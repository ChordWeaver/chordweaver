# -*- coding: utf-8 -*-
"""
La escuelita: la pantalla.

Arriba, el recorrido entero ---ocho unidades, una estación por lección y
la graduación al final---, que es lo primero que hay que ver para saber
dónde está uno. Abajo, a la izquierda, la lección: qué se explica y qué
dice el libro de eso; a la derecha, el ejercicio.

Lo que se enseña, en qué orden y cómo se corrige vive en
:mod:`engine.school`, que no sabe dibujar. Acá está sólo lo que se ve.

Como :mod:`analyzer` y :mod:`spectrum`, este módulo **no importa** ``app``:
la paleta y el escalador de fuentes llegan por parámetro, y lo que la
aplicación tiene que hacer ---abrir el libro, abrir el experimentador,
entregar logros, jugar la graduación--- llega como funciones.

Por qué el sistema es el del analizador
---------------------------------------
Los ejercicios de escritura usan :class:`staff.GrandStaff` tal cual, sin
ninguna versión propia. El alumno escribe exactamente donde escribiría en
el analizador, y lo que escribe se le pasa entero al analizador para
corregirlo: si la escuelita tuviera un pentagrama distinto, aprender acá
sería aprender otro programa.
"""

from __future__ import annotations

import random
import time
import tkinter as tk
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from engine import analysis, audio, book, harmonics, i18n
from engine import school as lessons_engine
from engine.i18n import tr, trf, trs
from staff import GRAND_VOICE_COUNT, VOICE_COLOURS, GrandStaff

#: Cómo se colorea cada clase de movimiento cuando la corrección lo señala.
#: Los mismos colores del analizador.
MOTION_COLOURS = {
    analysis.MOTION_CONTRARY: "#3F7D6E",
    analysis.MOTION_OBLIQUE: "#4A6FA5",
    analysis.MOTION_PARALLEL: "#C2554B",
    analysis.MOTION_SIMILAR: "#C08A2E",
    analysis.MOTION_STATIC: "#7A7264",
}

#: Ancho de la columna de la lección. Fijo, y con los párrafos envueltos a
#: un ancho fijo: un `wraplength` atado al `<Configure>` de su propio panel
#: cambia el alto, el alto reacomoda el panel y la ventana se cuelga ---es
#: la trampa que CLAUDE.md cuenta del experimentador---.
LESSON_WIDTH = 330
LESSON_WRAP = 292

#: Lo que mide el recorrido de arriba. Justo: en la ventana más chica el
#: sistema de dos pentagramas se lleva casi todo el alto del ejercicio, y
#: cada renglón que se ahorra acá es un renglón de corrección que se ve.
TRAIL_HEIGHT = 62

#: Cuánto se espera antes de volver a preguntar si terminó de sonar.
SOUND_POLL_MS = 140

#: Cuántas observaciones de la corrección entran a la vista. Más allá se
#: dice cuántas quedan: una lista de doce errores no se lee, y el primero ya
#: dice por dónde empezar.
MAX_REMARKS = 5

#: El alto del gráfico de la serie armónica.
TONE_HEIGHT = 236

#: Cuánto puede apretarse una negra en el pentagrama de la escuelita. Con
#: el piso de siempre, cuatro compases con corcheas no entraban al lado de
#: la lección en la ventana más chica y el último quedaba cortado.
QUARTER_FLOOR = 32.0

#: El ancho de un botón de customtkinter cuando no se le dice ninguno.
DEFAULT_OPTION_WIDTH = 140


def _strip_marks(text: str) -> str:
    """Un párrafo del libro sin los ``**`` de la entradilla."""
    return text.replace("**", "")


class School(ctk.CTkFrame):
    """La pantalla entera de la escuelita."""

    def __init__(self, master, colours: Dict[str, object],
                 progress: lessons_engine.Progress,
                 memory: Optional[dict] = None,
                 entry_written: Optional[Callable[[str], bool]] = None,
                 on_book: Optional[Callable[[str], None]] = None,
                 on_lab: Optional[Callable[[], None]] = None,
                 on_analysed: Optional[Callable[[object], None]] = None,
                 on_played: Optional[Callable[[], None]] = None,
                 on_finished: Optional[Callable[[], None]] = None,
                 **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.colours = colours
        self.font = colours.get("font", lambda f: f)
        self.progress = progress
        #: Lo que no se guarda en disco pero tiene que sobrevivir a ir al
        #: libro y volver: la lección abierta y lo que se estaba escribiendo
        #: en cada ejercicio. La pantalla se rearma entera al volver de un
        #: desvío, y sin esto abrir la cita del libro borraba el ejercicio.
        self.memory = memory if memory is not None else {}
        self.memory.setdefault("drafts", {})
        self.entry_written = entry_written or (lambda _key: True)
        self.on_book = on_book
        self.on_lab = on_lab
        self.on_analysed = on_analysed
        self.on_played = on_played
        self.on_finished = on_finished

        self.lesson: lessons_engine.Lesson = self._starting_lesson()
        self.exercise: lessons_engine.Exercise = self._starting_exercise()
        self.verdict: Optional[lessons_engine.Verdict] = None
        self.staff: Optional[GrandStaff] = None
        self._playing = None
        self._checking = None
        self._answered = ""
        self._hover_station = -1
        #: La práctica libre de lectura, mientras se practica: la clave, la
        #: racha y los tiempos. ``None`` es «no se está practicando».
        self._practice: Optional[dict] = None
        self._practice_return: Optional[lessons_engine.Exercise] = None
        self._random = random.Random()

        self.grid_columnconfigure(0, weight=0, minsize=LESSON_WIDTH)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.trail = tk.Canvas(self, height=TRAIL_HEIGHT, highlightthickness=0,
                               bd=0, bg=colours["surface"])
        self.trail.grid(row=0, column=0, columnspan=2, sticky="ew",
                        pady=(0, 10))
        self.trail.bind("<Configure>", lambda _e: self._draw_trail())
        self.trail.bind("<Motion>", self._trail_motion)
        self.trail.bind("<Leave>", lambda _e: self._trail_hover(-1))
        self.trail.bind("<Button-1>", self._trail_click)

        # Un marco quieto y no uno con scroll: la lección son dos párrafos y
        # una cita, y la barra de un marco con scroll se dibuja siempre,
        # haga falta o no ---una barra gris al lado de un texto que entra
        # entero se lee como que falta algo---.
        self.lesson_host = ctk.CTkFrame(self, fg_color="transparent",
                                        width=LESSON_WIDTH - 12)
        self.lesson_host.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        self.card = ctk.CTkFrame(self, fg_color=colours["panel"],
                                 corner_radius=14)
        self.card.grid(row=1, column=1, sticky="nsew")

        self._render_lesson()
        self._render_exercise()

    # -- dónde arrancar -----------------------------------------------------

    def _starting_lesson(self) -> lessons_engine.Lesson:
        remembered = lessons_engine.lesson(self.memory.get("lesson", ""))
        if remembered is not None:
            return remembered
        return self.progress.current()

    def _starting_exercise(self) -> lessons_engine.Exercise:
        remembered = lessons_engine.exercise(self.memory.get("exercise", ""))
        if remembered is not None and remembered in self.lesson.exercises:
            return remembered
        pending = [item for item in self.lesson.exercises
                   if not self.progress.has(item.key)]
        return pending[0] if pending else self.lesson.exercises[0]

    # -- utilidades ---------------------------------------------------------

    def _label(self, master, text: str, size: int = 12, weight: str = "",
               colour: str = "", wrap: int = 0, serif: bool = False,
               **kwargs) -> ctk.CTkLabel:
        # `serif` es la letra de los títulos del programa (Georgia), la misma
        # del libro: el título de la lección es un título como cualquier otro.
        spec = (("Georgia", size, "bold") if serif else
                ("Segoe UI Semibold" if weight == "bold" else "Segoe UI", size))
        return ctk.CTkLabel(master, text=text, font=self.font(spec),
                            text_color=colour or self.colours["text"],
                            wraplength=wrap, justify="left", anchor="w",
                            **kwargs)

    @staticmethod
    def _wipe(widget) -> None:
        for child in widget.winfo_children():
            child.destroy()

    def _button(self, master, text: str, command, accent: bool = False,
                width: int = 0, colour: str = "") -> ctk.CTkButton:
        colours = self.colours
        if accent:
            return ctk.CTkButton(
                master, text=text, command=command, height=32,
                width=width or 120, font=self.font(("Segoe UI Semibold", 12)),
                fg_color=colours["accent"],
                hover_color=colours["accent_hover"],
                text_color=colours["surface"])
        return ctk.CTkButton(
            master, text=text, command=command, height=32,
            width=width or 110, font=self.font(("Segoe UI", 12)),
            fg_color="transparent", border_width=1,
            border_color=colour or colours["muted"],
            text_color=colour or colours["text"],
            hover_color=colours["raised"])

    # -- el recorrido -------------------------------------------------------

    def _stations(self) -> List[Tuple[float, lessons_engine.Lesson, int]]:
        """Dónde va cada estación: ``(x, lección, unidad)``."""
        width = max(self.trail.winfo_width(), 600)
        left, right = 24.0, width - 190.0
        units = lessons_engine.UNITS
        count = sum(len(unit.lessons) for unit in units)
        gaps = len(units) - 1
        # Entre unidades queda el doble de aire que entre lecciones: es lo
        # que hace que el recorrido se lea como ocho tramos y no como una
        # fila de veintiocho puntos.
        step = (right - left) / max(1, (count - 1) + gaps)
        out, x = [], left
        for number, unit in enumerate(units):
            for index, item in enumerate(unit.lessons):
                out.append((x, item, number))
                x += step
            x += step
        return out

    def _draw_trail(self) -> None:
        canvas = self.trail
        canvas.delete("all")
        colours = self.colours
        stations = self._stations()
        if not stations:
            return
        line_y = 36
        faint = colours["faint"]
        accent = colours["accent"]
        # Las líneas primero, para que los círculos queden encima.
        for (x0, item0, unit0), (x1, _item1, unit1) in zip(stations,
                                                           stations[1:]):
            done = self.progress.lesson_done(item0)
            if unit0 == unit1:
                canvas.create_line(x0, line_y, x1, line_y, width=2,
                                   fill=accent if done else faint)
            else:
                canvas.create_line(x0, line_y, x1, line_y, width=1,
                                   fill=faint, dash=(2, 4))
        # Los nombres de las unidades, encima de su primera estación.
        current_unit = lessons_engine.unit_of(self.lesson.key)
        seen_units = set()
        for x, item, number in stations:
            if number in seen_units:
                continue
            seen_units.add(number)
            unit = lessons_engine.UNITS[number]
            colour = (accent if unit is current_unit
                      else colours["text"] if self.progress.unit_done(unit)
                      else colours["muted"])
            canvas.create_text(x - 7, 11, anchor="w",
                               text=f"{unit.numeral} · {tr(unit.short)}",
                               fill=colour,
                               font=self.font(("Segoe UI Semibold", 10)))
        for index, (x, item, _number) in enumerate(stations):
            opened = self.progress.lesson_open(item)
            done = self.progress.lesson_done(item)
            chosen = item.key == self.lesson.key
            if chosen:
                canvas.create_oval(x - 11, line_y - 11, x + 11, line_y + 11,
                                   outline=accent, width=2)
            if done:
                canvas.create_oval(x - 7, line_y - 7, x + 7, line_y + 7,
                                   fill=accent, outline=accent)
            elif opened:
                canvas.create_oval(x - 7, line_y - 7, x + 7, line_y + 7,
                                   fill=colours["surface"], outline=accent,
                                   width=2)
            else:
                canvas.create_oval(x - 6, line_y - 6, x + 6, line_y + 6,
                                   fill=colours["surface"], outline=faint,
                                   width=1)
            if index == self._hover_station:
                label = tr(item.title)
                canvas.create_text(x, line_y + 18, text=label,
                                   fill=colours["text"] if opened else faint,
                                   font=self.font(("Segoe UI", 10)))
        # La graduación, al final del camino. Una estrella apagada hasta que
        # se la vive: es la única estación que no es una lección.
        last_x = stations[-1][0]
        star_x = max(self.trail.winfo_width(), 600) - 60
        canvas.create_line(last_x + 12, line_y, star_x - 14, line_y,
                           fill=faint, dash=(2, 4))
        graduated = bool(self.progress.graduated)
        canvas.create_text(star_x, line_y, text="★",
                           fill=colours["gold"] if graduated else faint,
                           font=self.font(("Segoe UI Symbol", 20)))
        done, total = self.progress.counts()
        canvas.create_text(star_x, 11, anchor="center",
                           text=tr("Graduación"),
                           fill=colours["gold"] if graduated else colours["muted"],
                           font=self.font(("Segoe UI Semibold", 10)))
        canvas.create_text(star_x, line_y + 18,
                           text=trf("{done} de {total}", done=done,
                                    total=total),
                           fill=colours["muted"],
                           font=self.font(("Segoe UI", 10)))

    def _station_at(self, x: float, y: float) -> int:
        if not 20 <= y <= 54:
            return -1
        for index, (sx, _item, _unit) in enumerate(self._stations()):
            if abs(sx - x) <= 11:
                return index
        return -1

    def _trail_motion(self, event) -> None:
        self._trail_hover(self._station_at(event.x, event.y))

    def _trail_hover(self, index: int) -> None:
        if index == self._hover_station:
            return
        self._hover_station = index
        try:
            self.trail.configure(cursor="hand2" if index >= 0 else "")
        except tk.TclError:
            pass
        self._draw_trail()

    def _trail_click(self, event) -> None:
        index = self._station_at(event.x, event.y)
        if index < 0:
            return
        # Cualquier lección, aunque las anteriores no estén aprobadas: el
        # orden es el recomendado, no una cerradura. Las que vienen más
        # adelante se dibujan apagadas, pero se abren igual.
        self.open_lesson(self._stations()[index][1])

    # -- la lección ---------------------------------------------------------

    def open_lesson(self, item: lessons_engine.Lesson,
                    exercise: Optional[lessons_engine.Exercise] = None) -> None:
        self._save_draft()
        self.lesson = item
        if exercise is None:
            pending = [entry for entry in item.exercises
                       if not self.progress.has(entry.key)]
            exercise = pending[0] if pending else item.exercises[0]
        self.exercise = exercise
        self.memory["lesson"] = item.key
        self.memory["exercise"] = exercise.key
        self._draw_trail()
        self._render_lesson()
        self._render_exercise()

    def _render_lesson(self) -> None:
        host = self.lesson_host
        self._wipe(host)
        colours = self.colours
        item = self.lesson
        unit = lessons_engine.unit_of(item.key)
        self._label(host, trf("UNIDAD {numeral} · {title}",
                              numeral=unit.numeral,
                              title=tr(unit.title).upper()),
                    size=10, weight="bold", colour=colours["accent"]
                    ).pack(anchor="w", pady=(2, 2))
        self._label(host, tr(item.title), size=20, serif=True,
                    wrap=LESSON_WRAP).pack(anchor="w", pady=(0, 10))
        for paragraph in item.text:
            self._label(host, tr(paragraph), size=12,
                        colour=colours["text"], wrap=LESSON_WRAP
                        ).pack(anchor="w", pady=(0, 8))
        self._book_card(host, item)
        if unit.key == "lectura":
            self._button(host, tr("Práctica libre de lectura  →"),
                         self.open_practice, colour=colours["accent"],
                         width=LESSON_WIDTH - 40
                         ).pack(anchor="w", pady=(10, 0))
        if item.lab and self.on_lab is not None:
            self._button(host, tr("Abrir el experimentador  →"),
                         self.on_lab, colour=colours["gold"],
                         width=LESSON_WIDTH - 40
                         ).pack(anchor="w", pady=(10, 0))

    def _citation_open(self) -> bool:
        """Si el apartado que cita la lección en curso ya está escrito."""
        found = book.find(self.lesson.cite) if self.lesson else None
        if found is None:
            return True
        entry = found[1]
        return (not entry.locked_by) or bool(self.entry_written(entry.locked_by))

    def _book_card(self, host, item: lessons_engine.Lesson) -> None:
        """
        La cita del libro: el párrafo que sostiene la lección.

        Con los colores del libro ---papel, tinta, Georgia--- para que se
        lea como lo que es: no es la escuelita explicando, es el libro
        diciendo lo mismo con sus palabras. Si el apartado todavía no está
        escrito no se lo regala: se muestra cómo se escribe, igual que en el
        libro. Casi siempre lo escribe el ejercicio de esa misma lección.
        """
        colours = self.colours
        found = book.find(item.cite)
        if found is None:
            return
        chapter_index, entry = found
        chapter = book.CHAPTERS[chapter_index]
        written = (not entry.locked_by) or self.entry_written(entry.locked_by)
        card = ctk.CTkFrame(host, fg_color=colours["paper"],
                            border_width=1, border_color=colours["rule"],
                            corner_radius=12)
        card.pack(fill="x", pady=(6, 0))
        inner = tk.Frame(card, bg=colours["paper"])
        inner.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(inner, text=trf("DEL LIBRO · CAPÍTULO {numeral}",
                                 numeral=chapter.numeral),
                 font=self.font(("Georgia", 9)), bg=colours["paper"],
                 fg=colours["gold_dim"], anchor="w").pack(anchor="w")
        tk.Label(inner, text=tr(entry.heading),
                 font=self.font(("Georgia", 13, "bold")), bg=colours["paper"],
                 fg=colours["ink"], wraplength=LESSON_WRAP - 40,
                 justify="left", anchor="w").pack(anchor="w", pady=(2, 6))
        if written and 0 <= item.quote < len(entry.paragraphs):
            tk.Label(inner,
                     text="«" + _strip_marks(tr(entry.paragraphs[item.quote]))
                     + "»",
                     font=self.font(("Georgia", 11, "italic")),
                     bg=colours["paper"], fg=colours["ink_muted"],
                     wraplength=LESSON_WRAP - 40, justify="left",
                     anchor="w").pack(anchor="w")
        else:
            tk.Label(inner, text=tr("— sin anotar todavía —"),
                     font=self.font(("Georgia", 11, "italic")),
                     bg=colours["paper"], fg=colours["ink_faint"],
                     anchor="w").pack(anchor="w")
            if entry.hint:
                tk.Label(inner, text=tr(entry.hint),
                         font=self.font(("Georgia", 11)),
                         bg=colours["paper"], fg=colours["ink_faint"],
                         wraplength=LESSON_WRAP - 40, justify="left",
                         anchor="w").pack(anchor="w", pady=(4, 0))
        if self.on_book is not None:
            ctk.CTkButton(
                card, text=tr("Abrir en el libro  →"), height=28,
                font=self.font(("Georgia", 11)), fg_color="transparent",
                hover_color=colours["paper_edge"],
                text_color=colours["gold"], anchor="w",
                command=lambda key=entry.key: self.on_book(key)
            ).pack(anchor="w", padx=8, pady=(0, 10))

    # -- el ejercicio -------------------------------------------------------

    def open_exercise(self, item: lessons_engine.Exercise) -> None:
        self._save_draft()
        self.exercise = item
        self.memory["exercise"] = item.key
        self._render_exercise()

    def _render_exercise(self) -> None:
        if self._practice is not None:
            self._practice = None
            if self._practice_return is not None and \
                    self.exercise.key == lessons_engine.PRACTICE_KEY:
                self.exercise = self._practice_return
        card = self.card
        self._wipe(card)
        self.staff = None
        self.verdict = None
        self._answered = ""
        # Las voces que ofrecía el ejercicio anterior: sin vaciarlas, un Tab
        # en un ejercicio de elegir tocaba el menú de voces ya destruido.
        self._lanes_offered = []
        self.voice_menu = None
        self.dictation_button = None
        self.option_buttons: Dict[str, ctk.CTkButton] = {}
        colours = self.colours
        item = self.exercise
        lesson = self.lesson

        # Cuánto entra a lo ancho, medido una vez contra la ventana y no
        # atado al `<Configure>` del panel: un `wraplength` que sigue a su
        # propio panel lo agranda, el panel crece y la ventana se cuelga.
        # La pantalla se rearma entera al cambiar de ejercicio, así que
        # medir al armarla alcanza.
        try:
            width = self.winfo_toplevel().winfo_width()
        except tk.TclError:
            width = 1180
        self._wrap = max(560, width - LESSON_WIDTH - 130)

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 4))
        self.head = head
        position = lesson.exercises.index(item) + 1
        self._label(head, trf("EJERCICIO {n} DE {total}", n=position,
                              total=len(lesson.exercises)),
                    size=10, weight="bold", colour=colours["muted"]
                    ).pack(side="left")
        dots = ctk.CTkFrame(head, fg_color="transparent")
        dots.pack(side="left", padx=(10, 0))
        for entry in lesson.exercises:
            done = self.progress.has(entry.key)
            here = entry.key == item.key
            dot = ctk.CTkLabel(
                dots, text="●" if done or here else "○", width=16,
                font=self.font(("Segoe UI Symbol", 13 if here else 11)),
                text_color=(colours["accent"] if here
                            else colours["ok"] if done else colours["faint"]),
                cursor="hand2")
            dot.pack(side="left")
            dot.bind("<Button-1>", lambda _e, x=entry: self.open_exercise(x))
        self.passed_chip = self._label(
            head, tr("✓  Aprobado") if self.progress.has(item.key) else "",
            size=11, weight="bold", colour=colours["ok"])
        self.passed_chip.pack(side="right")

        self._label(card, tr(item.prompt), size=14, weight="bold",
                    wrap=self._wrap).pack(anchor="w", padx=20, pady=(2, 10))

        self.work = ctk.CTkFrame(card, fg_color="transparent")
        self.work.pack(fill="x", padx=14)
        self.controls = ctk.CTkFrame(card, fg_color="transparent")
        self.controls.pack(fill="x", padx=20, pady=(8, 4))
        self.status = self._label(card, "", size=11, colour=colours["muted"],
                                  wrap=self._wrap)
        # El renglón de estado sólo donde se escribe: ahí dice cómo se
        # escribe y qué nota hay bajo el mouse. En los de elegir no tiene nada
        # que decir y ocupaba un renglón que le hacía falta a la corrección.
        if item.kind in lessons_engine.WRITTEN:
            self.status.pack(anchor="w", padx=20)
        # Con scroll: en la ventana más chica el sistema se lleva casi todo
        # el alto y lo que queda para la corrección son dos renglones. Es lo
        # último que se empaqueta, así que es lo que se achica, y con scroll
        # achicarse no esconde nada.
        self.feedback = ctk.CTkScrollableFrame(card, fg_color="transparent",
                                               height=130)
        self.feedback.pack(fill="both", expand=True, padx=14, pady=(4, 12))

        if item.kind in lessons_engine.WRITTEN:
            self._build_staff(editable=True)
            self._build_writing_controls()
        elif item.kind == lessons_engine.TONE:
            self._build_tone_chart(self.work, item)
            self._build_choice_controls()
        elif item.kind == lessons_engine.HEAR:
            self._build_listening()
            self._build_choice_controls()
        else:
            self._build_staff(editable=False)
            self._mark_question()
            self._build_choice_controls()
        self._draw_trail()

    # -- el sistema ---------------------------------------------------------

    def _build_staff(self, editable: bool) -> None:
        colours = self.colours
        item = self.exercise
        staff = GrandStaff(
            self.work,
            colours={"surface": colours["surface"], "text": colours["text"],
                     "muted": colours["muted"], "accent": colours["accent"],
                     "glow": colours["glow"]},
            on_change=self._staff_changed, on_hover=self._hovered,
            figures=False)
        staff.quarter_floor = QUARTER_FLOOR
        staff.set_key(item.fifths, 4, 4)
        staff.set_metres([(1, 4, 4)])
        staff.duration = lessons_engine.FIGURE
        draft = self.memory["drafts"].get(item.key) if editable else None
        self._good = (draft if draft is not None
                      else lessons_engine.given_lines(item))
        self._loading = True
        staff.load(self._good)
        self._loading = False
        # Lo cargado no se deshace: el primer «deshacer» tiene que volver a
        # lo que había antes de la primera nota del alumno, no a un
        # pentagrama vacío.
        try:
            staff._past.clear()
        except AttributeError:
            pass
        lanes = lessons_engine.editable_lanes(item)
        staff.active = lanes[-1] if lanes else 0
        staff.pack(fill="x")
        self.staff = staff
        canvas = staff.canvas
        canvas.configure(takefocus=True)
        canvas.bind("<Enter>", lambda _e: canvas.focus_set(), add="+")
        canvas.bind("<Tab>", self._next_voice)
        canvas.bind("<Control-z>", self._undo_key)
        canvas.bind("<Control-Z>", self._undo_key)

    def _staff_changed(self) -> None:
        """
        Lo escrito cambió. Se mira en el próximo respiro, no acá.

        El aviso llega desde adentro de la escritura del pentagrama, a mitad
        de un click: deshacer desde acá mismo sería pisar la nota que el
        pentagrama todavía está terminando de anotar.
        """
        if getattr(self, "_loading", False):
            return
        if self._checking is not None:
            return
        self._checking = self.after_idle(self._guard)

    def _guard(self) -> None:
        """Devolver lo que no se podía tocar, y guardar el borrador."""
        self._checking = None
        staff = self.staff
        if staff is None:
            return
        self._refresh_signs()
        item = self.exercise
        touched = lessons_engine.tampered(item, staff.lines())
        if touched is not None:
            bar, lane = touched
            self._loading = True
            staff.undo()
            if lessons_engine.tampered(item, staff.lines()) is not None:
                # Deshacer no alcanzó ---la pila no llegaba tan atrás---:
                # se vuelve a lo último que estaba bien.
                staff.load(self._good)
            self._loading = False
            if item.kind in lessons_engine.WRITTEN:
                self._status(trf("{voice} del compás {bar} ya viene dado. "
                                 "Escribí en las otras voces.",
                                 voice=tr(lessons_engine.VOICE_NAMES[lane]),
                                 bar=bar), warn=True)
            else:
                self._status(tr("Este fragmento es para mirar. La respuesta "
                                "se elige abajo."), warn=True)
            return
        self._good = staff.lines()
        if item.kind in lessons_engine.WRITTEN:
            self.memory["drafts"][item.key] = self._good
            # Lo corregido deja de valer en cuanto se escribe otra cosa: las
            # marcas en el sistema señalarían una partitura que ya cambió.
            if self.verdict is not None:
                self.verdict = None
                staff.annotations = []
                staff.flags = []
                staff.motions = []
                staff.highlight = None
                staff.redraw()
                self._wipe(self.feedback)

    def _hovered(self, hit) -> None:
        if hit is None or self.staff is None:
            self._status("")
            return
        voice, position = hit
        try:
            index, duration, accidental = self.staff.voices[voice][position]
        except (IndexError, ValueError):
            return
        if index is None:
            return
        from staff import pitch_at          # noqa: PLC0415
        pitch = pitch_at(index, self.exercise.fifths, accidental)
        self._status(trf("{voice}: {note}",
                         voice=tr(lessons_engine.VOICE_NAMES[voice]),
                         note=lessons_engine.say_pitch(
                             pitch, self.exercise.fifths < 0)))

    def _mark_question(self) -> None:
        """Señalar en el sistema el compás del que habla la pregunta."""
        if self.staff is None:
            return
        span = lessons_engine.question_span(self.exercise)
        if span is not None:
            self.staff.highlight = span
        self.staff.redraw()

    def _voices_menu(self, master) -> None:
        item = self.exercise
        lanes = lessons_engine.editable_lanes(item)
        if not lanes:
            return
        self._lanes_offered = sorted(lanes, reverse=True)
        names = [lessons_engine.VOICE_NAMES[lane] for lane in self._lanes_offered]
        self._label(master, tr("Escribo la"), size=11,
                    colour=self.colours["muted"]).pack(side="left",
                                                       padx=(0, 6))
        self.voice_menu = ctk.CTkOptionMenu(
            master, values=trs(names), width=112, height=30,
            font=self.font(("Segoe UI", 12)),
            fg_color=self.colours["surface"],
            button_color=self.colours["surface"],
            button_hover_color=self.colours["accent_hover"],
            command=lambda _v: self._voice_chosen())
        start = self.staff.active if self.staff is not None else lanes[-1]
        self.voice_menu.set(tr(lessons_engine.VOICE_NAMES[start]))
        self.voice_menu.pack(side="left", padx=(0, 12))
        swatch = ctk.CTkLabel(master, text="●", width=14,
                              font=self.font(("Segoe UI", 14)),
                              text_color=VOICE_COLOURS[GRAND_VOICE_COUNT - 1
                                                       - start])
        swatch.pack(side="left", padx=(0, 10))
        self._swatch = swatch

    def _voice_chosen(self) -> None:
        if self.staff is None:
            return
        name = i18n.untr(self.voice_menu.get())
        if name in lessons_engine.VOICE_NAMES:
            lane = lessons_engine.VOICE_NAMES.index(name)
            self.staff.active = lane
            self.staff.redraw()
            try:
                self._swatch.configure(
                    text_color=VOICE_COLOURS[GRAND_VOICE_COUNT - 1 - lane])
            except (tk.TclError, AttributeError):
                pass

    def _next_voice(self, _event=None) -> str:
        lanes = getattr(self, "_lanes_offered", [])
        if not lanes or self.staff is None or self.voice_menu is None:
            return "break"
        current = self.staff.active
        following = lanes[(lanes.index(current) + 1) % len(lanes)] \
            if current in lanes else lanes[0]
        self.voice_menu.set(tr(lessons_engine.VOICE_NAMES[following]))
        self._voice_chosen()
        return "break"

    def _undo_key(self, _event=None) -> str:
        button = getattr(self, "undo_button", None)
        if button is not None:
            button.invoke()
        return "break"

    def _build_writing_controls(self) -> None:
        bar = self.controls
        item = self.exercise
        self._voices_menu(bar)
        self.play_button = self._button(bar, tr("▶  Escuchar"), self._play)
        self.play_button.pack(side="left", padx=(0, 6))
        self.undo_button = self._button(bar, tr("↶  Deshacer"), self._undo)
        self.undo_button.pack(side="left", padx=(0, 6))
        self._button(bar, tr("Empezar de nuevo"), self._restart,
                     width=130).pack(side="left")
        self.check_button = self._button(bar, tr("Corregir"), self._check,
                                         accent=True, width=128)
        self.check_button.pack(side="right")
        self._next_slot(bar)
        self._build_tools()
        self._status(self._writing_hint())

    def _writing_hint(self) -> str:
        item = self.exercise
        if item.param("durations"):
            return tr("Elegí la figura y hacé click para escribirla. Click "
                      "derecho borra.")
        if item.param("accidentals"):
            return tr("Elegí el signo antes de hacer click: vale para esa "
                      "nota sola. Click derecho borra.")
        if item.param("dictation"):
            return tr("Escuchá el dictado las veces que haga falta. Click "
                      "escribe una redonda y click derecho borra.")
        return tr("Click escribe una redonda en la voz elegida, click "
                  "derecho borra y Tab cambia de voz.")

    def _build_tools(self) -> None:
        """
        Las figuras y los signos, sólo en los ejercicios que los piden. En
        los demás todo es una redonda natural, y ofrecer más sería ofrecer
        maneras de equivocarse que no se están enseñando.
        """
        item = self.exercise
        durations = item.param("durations", ())
        signs = bool(item.param("accidentals"))
        dictation = bool(item.param("dictation"))
        self.sign_buttons: Dict[Optional[int], ctk.CTkButton] = {}
        self.dictation_button = None
        if not durations and not signs and not dictation:
            return
        colours = self.colours
        tools = ctk.CTkFrame(self.card, fg_color="transparent")
        tools.pack(fill="x", padx=20, pady=(4, 0), before=self.controls)
        if dictation:
            # Lo que se escucha para escribir. «Escuchar», abajo, toca lo que
            # uno ya escribió, para compararlo.
            self.dictation_button = self._button(
                tools, tr("▶  Dictado"), self._play_dictation, accent=True,
                width=130)
            self.dictation_button.pack(side="left")
        if durations:
            self._label(tools, tr("Figura"), size=11,
                        colour=colours["muted"]).pack(side="left", padx=(0, 6))
            names = {}
            for value in durations:
                name = tr(lessons_engine.FIGURE_NAMES[value])
                names[name[:1].upper() + name[1:]] = value
            self._figures = names
            chooser = ctk.CTkSegmentedButton(
                tools, values=list(names), height=30,
                font=self.font(("Segoe UI", 12)),
                fg_color=colours["surface"],
                selected_color=colours["accent"],
                selected_hover_color=colours["accent_hover"],
                unselected_color=colours["surface"],
                unselected_hover_color=colours["raised"],
                text_color=colours["text"],
                command=self._figure_chosen)
            start = 1.0 if 1.0 in durations else durations[0]
            chooser.set(next(n for n, v in names.items() if v == start))
            chooser.pack(side="left", padx=(0, 16))
            if self.staff is not None:
                self.staff.duration = start
        if signs:
            self._label(tools, tr("Signo"), size=11,
                        colour=colours["muted"]).pack(side="left", padx=(0, 6))
            for value, glyph in ((1, "♯"), (-1, "♭"), (0, "♮")):
                button = ctk.CTkButton(
                    tools, text=glyph, width=36, height=30,
                    font=self.font(("Segoe UI Symbol", 15)),
                    fg_color="transparent", border_width=1,
                    border_color=colours["muted"],
                    text_color=colours["text"],
                    hover_color=colours["raised"],
                    command=lambda v=value: self._sign_chosen(v))
                button.pack(side="left", padx=2)
                self.sign_buttons[value] = button

    def _figure_chosen(self, name: str) -> None:
        if self.staff is not None:
            self.staff.duration = self._figures.get(name, lessons_engine.FIGURE)

    def _sign_chosen(self, value: int) -> None:
        """Un signo para la próxima nota; apretarlo de nuevo lo saca."""
        if self.staff is None:
            return
        self.staff.pending = None if self.staff.pending == value else value
        self._refresh_signs()

    def _refresh_signs(self) -> None:
        """Encender el signo elegido. Escrita la nota, el pentagrama lo
        suelta y acá se apaga."""
        chosen = self.staff.pending if self.staff is not None else None
        for value, button in getattr(self, "sign_buttons", {}).items():
            on = value == chosen
            try:
                button.configure(
                    fg_color=self.colours["accent"] if on else "transparent",
                    border_color=(self.colours["accent"] if on
                                  else self.colours["muted"]))
            except tk.TclError:
                pass

    def _undo(self) -> None:
        if self.staff is not None:
            self.staff.undo()

    def _restart(self) -> None:
        if self.staff is None:
            return
        self.memory["drafts"].pop(self.exercise.key, None)
        self._good = lessons_engine.given_lines(self.exercise)
        self._loading = True
        self.staff.load(self._good)
        self._loading = False
        self.staff.annotations = []
        self.staff.flags = []
        self.staff.motions = []
        self.staff.highlight = None
        self.staff.redraw()
        self.verdict = None
        self._wipe(self.feedback)

    # -- escuchar -----------------------------------------------------------

    def _events(self) -> List[Tuple[int, float, float]]:
        lines = (self.staff.lines() if self.staff is not None
                 else lessons_engine.given_lines(self.exercise))
        events = []
        for line in lines:
            moment = 0.0
            for pitch, duration in line:
                if pitch is not None and duration > 0:
                    events.append((pitch, moment, duration))
                moment += duration
        events.sort(key=lambda event: (event[1], event[0]))
        return events

    def _play_dictation(self) -> None:
        """Tocar la melodía del dictado, la que hay que escribir."""
        item = self.exercise
        lines = lessons_engine.given_lines(item)
        lines[item.param("lane", lessons_engine.SOPRANO)] = [
            (pitch, lessons_engine.FIGURE) for pitch in item.param("pitches")]
        events = []
        for line in lines:
            moment = 0.0
            for pitch, duration in line:
                if pitch is not None:
                    events.append((pitch, moment, duration))
                moment += duration
        self._play(sorted(events, key=lambda e: (e[1], e[0])))

    def _play(self, events=None) -> None:
        if self._playing is not None and self._playing.is_alive():
            return
        item = self.exercise
        if item.kind == lessons_engine.TONE:
            self._playing = harmonics.play(lessons_engine.spectrum_for(item))
        else:
            events = events or self._events()
            if not events:
                self._status(tr("Todavía no hay nada escrito para escuchar."))
                return
            self._playing = audio.play_chords([], [], voices=events)
        if self.on_played is not None:
            self.on_played()
        for button in self._play_buttons():
            try:
                button.configure(text=tr("♪  Sonando…"), state="disabled")
            except tk.TclError:
                pass
        self._watch_sound()

    def _play_buttons(self):
        found = []
        for name in ("play_button", "listen_button", "dictation_button"):
            button = getattr(self, name, None)
            if button is not None:
                found.append(button)
        return found

    def _watch_sound(self) -> None:
        """
        Preguntar desde el hilo principal si el sonido terminó.

        El hilo del sonido no toca Tk ---igual que en el analizador y en el
        experimentador---: el botón se devuelve desde acá.
        """
        thread = self._playing
        if thread is not None and thread.is_alive():
            self.after(SOUND_POLL_MS, self._watch_sound)
            return
        for button in self._play_buttons():
            label = (tr("▶  Dictado")
                     if button is getattr(self, "dictation_button", None)
                     else tr("▶  Escuchar"))
            try:
                button.configure(text=label, state="normal")
            except tk.TclError:
                pass

    def _build_listening(self) -> None:
        """
        El lugar de la partitura, mientras no se la puede ver.

        Un ejercicio de oído no muestra el fragmento hasta que se contesta:
        con la partitura a la vista se contesta mirando, y lo que se quería
        practicar era escuchar.
        """
        colours = self.colours
        panel = ctk.CTkFrame(self.work, fg_color=colours["surface"],
                             corner_radius=12, height=200)
        panel.pack(fill="x", pady=(0, 4))
        panel.pack_propagate(False)
        self.listen_panel = panel
        middle = ctk.CTkFrame(panel, fg_color="transparent")
        middle.place(relx=0.5, rely=0.5, anchor="center")
        self.listen_button = ctk.CTkButton(
            middle, text=tr("▶  Escuchar"), width=180, height=44,
            corner_radius=22, font=self.font(("Segoe UI Semibold", 14)),
            fg_color=colours["accent"], hover_color=colours["accent_hover"],
            text_color=colours["surface"], command=self._play)
        self.listen_button.pack()
        self._label(middle, tr("La partitura aparece cuando contestes."),
                    size=11, colour=colours["muted"]).pack(pady=(10, 0))

    def _reveal(self) -> None:
        """Mostrar el fragmento de un ejercicio de oído, ya contestado."""
        panel = getattr(self, "listen_panel", None)
        if panel is None:
            return
        self.listen_panel = None
        self.listen_button = None
        panel.destroy()
        self._build_staff(editable=False)

    # -- la serie armónica --------------------------------------------------

    def _build_tone_chart(self, master, item) -> None:
        """
        La serie, dibujada a escala como en el experimentador y en el libro:
        barras igualmente espaciadas y alturas que caen como uno sobre ene.

        La barra de la pregunta va en el color de la escuelita y con un
        signo de pregunta; en el ejercicio de oído no se dibuja ninguna más
        que la fundamental, porque el gráfico contestaría por el oído.
        """
        colours = self.colours
        canvas = tk.Canvas(master, height=TONE_HEIGHT, highlightthickness=0,
                           bd=0, bg=colours["surface"])
        canvas.pack(fill="x", pady=(0, 4))
        self.tone_canvas = canvas
        canvas.bind("<Configure>", lambda _e: self._draw_tone(canvas, item))

    def _draw_tone(self, canvas, item) -> None:
        canvas.delete("all")
        colours = self.colours
        width = max(canvas.winfo_width(), 400)
        left, right, top, floor = 56, width - 30, 22, TONE_HEIGHT - 54
        spectrum = lessons_engine.spectrum_for(item)
        base = spectrum.fundamental
        hidden = bool(item.param("hidden"))
        asked = lessons_engine.asked_partial(item)
        show_names = item.rule == "first_interval"
        count = harmonics.PARTIAL_COUNT
        span = base * (count + 0.6)

        def x_for(freq: float) -> float:
            return left + (right - left) * freq / span

        canvas.create_line(left, floor, right, floor, fill=colours["faint"])
        canvas.create_text(right, floor + 38, anchor="e",
                           text=tr("frecuencia →"), fill=colours["faint"],
                           font=self.font(("Segoe UI", 9)))
        for partial in spectrum.partials:
            number = partial.number
            if hidden and number != 1:
                continue
            freq = partial.frequency(base)
            x = x_for(freq)
            gain = 1.0 / number
            height = (floor - top) * gain
            is_asked = number == asked
            colour = colours["accent"] if is_asked else colours["muted"]
            canvas.create_rectangle(x - 6, floor - height, x + 6, floor,
                                    fill=colour, outline="")
            canvas.create_text(x, floor + 12, text=str(number),
                               fill=colours["text"] if is_asked
                               else colours["muted"],
                               font=self.font(("Segoe UI Semibold", 10)))
            if is_asked:
                canvas.create_text(x, floor - height - 14, text="?",
                                   fill=colours["accent"],
                                   font=self.font(("Segoe UI Semibold", 16)))
            elif number == 1 and not show_names:
                # Con los nombres a la vista, el del primero va en el mismo
                # lugar y los dos se encimaban.
                canvas.create_text(x, floor + 26,
                                   text=f"{int(round(freq))} Hz",
                                   fill=colours["muted"],
                                   font=self.font(("Segoe UI", 9)))
            if show_names:
                note, _cents = harmonics.nearest_note(freq)
                canvas.create_text(x, floor + 26,
                                   text=lessons_engine.say_pitch(note),
                                   fill=colours["muted"],
                                   font=self.font(("Segoe UI", 9)))
        if hidden:
            canvas.create_text(x_for(base * 6.5), (top + floor) / 2,
                               text="?", fill=colours["accent"],
                               font=self.font(("Segoe UI Semibold", 30)))
        canvas.create_text(left - 10, top, anchor="e", text=tr("amplitud"),
                           fill=colours["faint"],
                           font=self.font(("Segoe UI", 9)), angle=90)

    # -- elegir -------------------------------------------------------------

    def _build_choice_controls(self) -> None:
        colours = self.colours
        bar = self.controls
        item = self.exercise
        if item.kind != lessons_engine.HEAR:
            self.play_button = self._button(bar, tr("▶  Escuchar"),
                                            self._play)
            self.play_button.pack(side="left", padx=(0, 12))
        # Las respuestas van al lado de «Escuchar», y de a dos por renglón
        # cuando los rótulos son largos ---«Treinta y una centésimas por
        # debajo»---: cuatro así en fila no entran en la ventana más chica.
        labels = [lessons_engine.option_label(option)
                  for option in item.options]
        widths = self._option_widths(labels)
        columns = self._option_columns(widths)
        options = ctk.CTkFrame(bar, fg_color="transparent")
        options.pack(side="left", fill="x", expand=True)
        for position, option in enumerate(item.options):
            button = ctk.CTkButton(
                options, text=labels[position], height=34,
                # A la medida del rótulo: con el ancho de fábrica de
                # customtkinter, las siete notas no entraban en un renglón.
                width=widths[position],
                font=self.font(("Segoe UI", 12)),
                fg_color=colours["surface"], hover_color=colours["raised"],
                border_width=1, border_color=colours["border"],
                text_color=colours["text"], corner_radius=17,
                command=lambda value=option.value: self._choose(value))
            button.grid(row=position // columns, column=position % columns,
                        sticky="w", padx=(0, 8), pady=3)
            self.option_buttons[option.value] = button
        self._next_slot(bar)

    def _option_widths(self, labels) -> List[int]:
        """
        El ancho de cada respuesta, medido con la letra de verdad y no
        contando caracteres: «Cruce de voces» y «Salto de tritono en una
        voz» no miden lo mismo por letra.
        """
        try:
            # `font measure` y no un `tkfont.Font`: `app.py` anula su
            # `__del__`, así que cada uno creado acá quedaba vivo en Tcl.
            spec = self.font(("Segoe UI", 12))
            widths = [int(self.tk.call("font", "measure", spec, text)) + 44
                      for text in labels]
        except (tk.TclError, TypeError):
            widths = [8 * len(text) + 44 for text in labels]
        # El ancho de fábrica de customtkinter mientras entren todas en un
        # renglón, que es como se vieron siempre; si no, cada una a su
        # medida, que es lo que deja las siete notas en fila.
        room = self._wrap - 150
        if sum(max(DEFAULT_OPTION_WIDTH, w) + 8 for w in widths) <= room:
            return [max(DEFAULT_OPTION_WIDTH, w) for w in widths]
        return [max(64, w) for w in widths]

    def _option_columns(self, widths) -> int:
        """
        Cuántas respuestas entran por renglón al lado de «Escuchar». Todas en
        un renglón si entran ---ahorra un renglón que en la ventana más chica
        es el de la corrección---, y si no, de a dos.
        """
        room = self._wrap - 150
        return len(widths) if sum(w + 8 for w in widths) <= room else 2

    def _choose(self, value: str) -> None:
        if self._practice is not None:
            self._practice_choose(value)
            return
        item = self.exercise
        verdict = lessons_engine.grade(item, chosen=value)
        self.verdict = verdict
        self._answered = value
        colours = self.colours
        # Lo equivocado se apaga y se puede volver a probar; lo correcto no
        # se dice hasta acertarlo. La corrección de una respuesta mala dice
        # qué tiene de malo esa, que es lo que enseña algo ---decir la buena
        # convertía el segundo intento en copiar---.
        if not verdict.passed:
            button = self.option_buttons.get(value)
            if button is not None:
                button.configure(border_color=colours["error"],
                                 text_color=colours["error"],
                                 state="disabled")
            self._show_verdict(verdict)
            return
        for key, button in self.option_buttons.items():
            if key == value:
                button.configure(border_color=colours["ok"],
                                 text_color=colours["ok"])
            else:
                button.configure(state="disabled",
                                 text_color=colours["faint"])
        if item.kind == lessons_engine.HEAR:
            self._reveal()
        if verdict.result is not None and self.staff is not None:
            self._annotate(verdict)
        self._show_verdict(verdict)

    # -- corregir -----------------------------------------------------------

    def _check(self) -> None:
        if self.staff is None:
            return
        item = self.exercise
        lines = self.staff.lines()
        verdict = lessons_engine.grade(item, lines)
        self.verdict = verdict
        if verdict.result is not None and self.on_analysed is not None:
            # Lo que el alumno escribió vale lo mismo que lo que escribe en
            # el analizador: si cerró una cadencia plagal, cerró una cadencia
            # plagal, y el logro ---y el apartado del libro que abre--- es
            # suyo. Sólo lo que entrega, nunca el fragmento de partida.
            before = self._citation_open()
            self.on_analysed(verdict.result)
            # Si eso abrió el apartado que cita la lección, la cita se
            # muestra ya y no recién al aprobar la lección entera.
            if self._citation_open() != before:
                self._render_lesson()
        self._annotate(verdict)
        self._show_verdict(verdict)

    def _annotate(self, verdict: lessons_engine.Verdict) -> None:
        """
        Escribir la corrección sobre el sistema: el cifrado que leyó el
        analizador arriba, y en rojo dónde está lo que hay que arreglar.
        """
        staff = self.staff
        result = verdict.result
        if staff is None:
            return
        figure = lessons_engine.FIGURE
        annotations = []
        if result is not None:
            for segment in result.segments:
                rows = segment.figure.split("/") if segment.figure else []
                annotations.append((segment.start, segment.symbol, rows))
        staff.annotations = annotations
        flags = []
        for remark in verdict.remarks:
            if remark.severity == "grave" and remark.bar:
                flags.append(((remark.bar - 1) * figure,
                              self.colours["error"]))
        staff.flags = flags
        staff.motions = self._motions(verdict)
        # Se resalta lo primero que hay que arreglar; si no hay nada, lo
        # primero que la corrección explica ---el compás por el que
        # preguntaba el ejercicio---.
        first = (next((r for r in verdict.remarks
                       if r.severity == "grave" and r.bar), None)
                 or next((r for r in verdict.remarks if r.bar), None))
        staff.highlight = (self._span(first) if first is not None else None)
        item = self.exercise
        if verdict.passed and item.param("at") is not None:
            # La pregunta era por una nota y no por el compás entero.
            staff.highlight = lessons_engine.question_span(item)
        staff.redraw()

    def _motions(self, verdict) -> list:
        """Los movimientos del par de voces que el ejercicio mira."""
        item = self.exercise
        result = verdict.result
        pair = item.param("pair")
        if result is None or not pair:
            return []
        low, high = pair
        names = [part.name for part in result.score.parts]
        try:
            a = names.index(lessons_engine.VOICE_NAMES[low])
            b = names.index(lessons_engine.VOICE_NAMES[high])
        except ValueError:
            return []
        key = (min(a, b), max(a, b))
        out = []
        for report in result.motions:
            kind = report.pairs.get(key)
            if not kind:
                continue
            ways = report.ways.get(key, (0, 0))
            moment = report.bar_index * lessons_engine.FIGURE
            out.append((moment, low, high, ways[0], ways[1],
                        MOTION_COLOURS.get(kind, self.colours["muted"])))
        return out

    @staticmethod
    def _span(remark) -> Tuple[float, float]:
        figure = lessons_engine.FIGURE
        last = max(remark.bar, remark.until or remark.bar)
        return ((remark.bar - 1) * figure, last * figure)

    def _show_verdict(self, verdict: lessons_engine.Verdict) -> None:
        colours = self.colours
        box = self.feedback
        self._wipe(box)
        item = self.exercise
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x", pady=(2, 6))
        if verdict.passed:
            self._label(head, tr("✓  Bien"), size=15, weight="bold",
                        colour=colours["ok"]).pack(side="left")
            first_time = self.progress.mark_passed(item.key)
            self.passed_chip.configure(text=tr("✓  Aprobado"))
            if first_time:
                self._passed_now()
        else:
            self._label(head, tr("✗  Todavía no"), size=15, weight="bold",
                        colour=colours["error"]).pack(side="left")
            if item.kind in lessons_engine.WRITTEN:
                self._label(head, tr("corregí y volvé a apretar «Corregir»"),
                            size=11, colour=colours["muted"]
                            ).pack(side="left", padx=(10, 0))
        # Lo grave primero: es lo que impide aprobar. Después lo que está
        # bien, que es lo que explica.
        order = {"grave": 0, "nota": 1, "bien": 2}
        remarks = sorted(verdict.remarks, key=lambda r: order.get(r.severity, 3))
        # La columna del lugar sólo si alguna observación tiene compás: en
        # los ejercicios de elegir ninguna tiene, y la columna vacía le
        # robaba ancho al texto, que se partía en más renglones de los que
        # entran.
        self._located = any(remark.bar for remark in remarks)
        for remark in remarks[:MAX_REMARKS]:
            self._remark_row(box, remark)
        if len(remarks) > MAX_REMARKS:
            self._label(box, trf("y {count} más.",
                                 count=len(remarks) - MAX_REMARKS),
                        size=11, colour=colours["muted"]).pack(anchor="w")
        self._refresh_next()

    def _remark_row(self, master, remark) -> None:
        colours = self.colours
        colour = {"grave": colours["error"], "nota": colours["muted"],
                  "bien": colours["ok"]}.get(remark.severity,
                                             colours["muted"])
        row = tk.Frame(master, bg=colours["panel"])
        row.pack(fill="x", pady=2)
        tk.Frame(row, bg=colour, width=3).pack(side="left", fill="y",
                                                padx=(0, 10))
        # La columna del lugar va siempre, aunque esté vacía: sin ella, una
        # observación sin compás arrancaba más a la izquierda que las demás
        # y la lista se leía torcida.
        where = ""
        if remark.bar:
            where = (trf("c. {bar}", bar=remark.bar) if not remark.until
                     or remark.until == remark.bar else
                     trf("c. {bar}→{until}", bar=remark.bar,
                         until=remark.until))
            if remark.voices:
                where += " · " + " / ".join(tr(v) for v in remark.voices)
        chip = tk.Label(row, text=where, bg=colours["panel"],
                        fg=colour, font=self.font(("Segoe UI Semibold", 10)),
                        anchor="w", width=22)
        if getattr(self, "_located", True):
            chip.pack(side="left", anchor="n")
        if remark.bar:
            for widget in (row, chip):
                widget.bind("<Button-1>",
                            lambda _e, r=remark: self._point_at(r))
            try:
                chip.configure(cursor="hand2")
            except tk.TclError:
                pass
        text = tk.Label(row, text=remark.text, bg=colours["panel"],
                        fg=colours["text"] if remark.severity == "grave"
                        else colours["muted"],
                        font=self.font(("Segoe UI", 11)),
                        wraplength=max(360, self._wrap - (
                            210 if getattr(self, "_located", True) else 40)),
                        justify="left", anchor="w")
        text.pack(side="left", fill="x", anchor="n")
        if remark.bar:
            text.bind("<Button-1>", lambda _e, r=remark: self._point_at(r))

    def _point_at(self, remark) -> None:
        """Resaltar en el sistema el tramo del que habla una observación."""
        if self.staff is None or not remark.bar:
            return
        self.staff.highlight = self._span(remark)
        self.staff.redraw()

    # -- avanzar -------------------------------------------------------------

    def _next_slot(self, _bar=None) -> None:
        """
        El lugar del «Siguiente», que aparece cuando hay a dónde ir.

        Arriba, en el renglón de los puntos y del «Aprobado», y no abajo con
        los mandos: es navegación entre ejercicios, igual que los puntos, y
        abajo competía por el ancho con las respuestas.
        """
        self.next_button = self._button(self.head, tr("Siguiente  →"),
                                        self._go_next, width=118)
        self._refresh_next()

    def _refresh_next(self) -> None:
        button = getattr(self, "next_button", None)
        if button is None:
            return
        target = self._following()
        ready = self.progress.has(self.exercise.key) and target is not None
        try:
            # Por quién lo administra y no por si se ve: recién armada la
            # pantalla todavía no se ve nada, y preguntando eso se lo
            # empaquetaba dos veces o no se lo sacaba nunca.
            packed = bool(button.winfo_manager())
            if ready and not packed:
                button.pack(side="right", padx=(0, 14))
            elif not ready and packed:
                button.pack_forget()
        except tk.TclError:
            pass

    def _following(self):
        """El ejercicio que sigue: en esta lección, o en la próxima."""
        items = lessons_engine.exercises()
        if self.exercise not in items:
            return None
        index = items.index(self.exercise)
        if index + 1 >= len(items):
            return None
        following = items[index + 1]
        if lessons_engine.lesson_of(following.key) is None:
            return None
        return following

    def _go_next(self) -> None:
        following = self._following()
        if following is None:
            return
        holder = lessons_engine.lesson_of(following.key)
        if holder is not None and holder.key != self.lesson.key:
            self.open_lesson(holder, following)
        else:
            self.open_exercise(following)

    def _passed_now(self) -> None:
        """
        Un ejercicio recién aprobado: el recorrido se entera, la cita del
        libro puede haberse escrito ---el ejercicio la escribe---, y si era
        el último, se avisa para la graduación.
        """
        self._draw_trail()
        if self.lesson_done_now():
            self._render_lesson()
        if self.progress.graduation_due() and self.on_finished is not None:
            # Con un respiro: que se alcance a ver el «Bien» antes de que la
            # pantalla se apague para la ceremonia.
            self.after(1400, self.on_finished)

    def lesson_done_now(self) -> bool:
        return self.progress.lesson_done(self.lesson)

    # -- la práctica libre de lectura ----------------------------------------

    #: Cuánto se ve el «bien» antes de la nota siguiente.
    PRACTICE_PAUSE_MS = 650

    #: Las claves de la práctica, como se leen en el selector.
    PRACTICE_CLEF_LABELS = (("sol", "Clave de sol"), ("fa", "Clave de fa"),
                            ("ambas", "Las dos"))

    def open_practice(self) -> None:
        """Notas al azar, una por vez, sin fin y sin contar para nada."""
        self._save_draft()
        if self._practice is None:
            self._practice_return = self.exercise
        clef = self.memory.get("practice_clef", "sol")
        if clef not in lessons_engine.PRACTICE_CLEFS:
            clef = "sol"
        self._render_practice(clef)

    def _render_practice(self, clef: str) -> None:
        card = self.card
        self._wipe(card)
        self.staff = None
        self.verdict = None
        self.option_buttons = {}
        colours = self.colours
        self._practice = {"clef": clef, "streak": 0, "times": [],
                          "started": 0.0, "missed": False, "previous": None}
        self.exercise = lessons_engine.practice_exercise(
            clef, self._random)

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 4))
        self.head = head
        self._label(head, tr("PRÁCTICA LIBRE · NO CUENTA PARA LA GRADUACIÓN"),
                    size=10, weight="bold", colour=colours["muted"]
                    ).pack(side="left")
        self._button(head, tr("←  Volver a la lección"), self._leave_practice,
                     width=170).pack(side="right")

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(4, 8))
        names = {tr(label): key for key, label in self.PRACTICE_CLEF_LABELS}
        selector = ctk.CTkSegmentedButton(
            row, values=list(names), height=30,
            font=self.font(("Segoe UI", 12)), fg_color=colours["surface"],
            selected_color=colours["accent"],
            selected_hover_color=colours["accent_hover"],
            unselected_color=colours["surface"],
            unselected_hover_color=colours["raised"],
            text_color=colours["text"],
            command=lambda name: self._practice_clef(names[name]))
        selector.set(next(n for n, k in names.items() if k == clef))
        selector.pack(side="left")
        self.practice_stats = self._label(row, "", size=12,
                                          colour=colours["text"])
        self.practice_stats.pack(side="right")

        self._label(card, tr("¿Qué nota es?"), size=14, weight="bold",
                    wrap=getattr(self, "_wrap", 560)
                    ).pack(anchor="w", padx=20, pady=(2, 10))
        self.work = ctk.CTkFrame(card, fg_color="transparent")
        self.work.pack(fill="x", padx=14)
        self.controls = ctk.CTkFrame(card, fg_color="transparent")
        self.controls.pack(fill="x", padx=20, pady=(8, 4))
        self.status = self._label(card, "", size=11, colour=colours["muted"])
        self.feedback = ctk.CTkScrollableFrame(card, fg_color="transparent",
                                               height=130)
        self.feedback.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self._build_staff(editable=False)
        self._build_choice_controls()
        self._practice["started"] = time.monotonic()
        self._practice_show_stats()
        self._draw_trail()

    def _practice_clef(self, clef: str) -> None:
        self.memory["practice_clef"] = clef
        self._render_practice(clef)

    def _practice_show_stats(self) -> None:
        state = self._practice
        if state is None:
            return
        times = state["times"][-10:]
        fields = dict(streak=state["streak"],
                      best=self.progress.practice_best)
        if times:
            seconds = sum(times) / len(times)
            text = trf("Racha {streak}  ·  mejor {best}  ·  {seconds} s por "
                       "nota", seconds=(f"{seconds:.1f}" if i18n.language()
                                        == "en" else
                                        f"{seconds:.1f}".replace(".", ",")),
                       **fields)
        else:
            text = trf("Racha {streak}  ·  mejor {best}", **fields)
        try:
            self.practice_stats.configure(text=text)
        except tk.TclError:
            pass

    def _practice_choose(self, value: str) -> None:
        state = self._practice
        item = self.exercise
        verdict = lessons_engine.grade(item, chosen=value)
        colours = self.colours
        button = self.option_buttons.get(value)
        self._wipe(self.feedback)
        if not verdict.passed:
            state["streak"] = 0
            state["missed"] = True
            if button is not None:
                button.configure(border_color=colours["error"],
                                 text_color=colours["error"],
                                 state="disabled")
            for remark in verdict.remarks[:MAX_REMARKS]:
                self._remark_row(self.feedback, remark)
            self._practice_show_stats()
            return
        if not state["missed"]:
            state["streak"] += 1
            state["times"].append(time.monotonic() - state["started"])
            self.progress.record_practice(state["streak"])
        for key, other in self.option_buttons.items():
            other.configure(state="disabled",
                            text_color=(colours["ok"] if key == value
                                        else colours["faint"]),
                            border_color=(colours["ok"] if key == value
                                          else colours["border"]))
        self._located = False
        self._remark_row(self.feedback, verdict.remarks[0])
        self._practice_show_stats()
        self.after(self.PRACTICE_PAUSE_MS, self._practice_next)

    def _practice_next(self) -> None:
        """Otra nota en el mismo pentagrama, sin rearmar la pantalla."""
        state = self._practice
        if state is None or self.staff is None:
            return
        previous = self.exercise.chords[0][self.exercise.param("lane")]
        self.exercise = lessons_engine.practice_exercise(
            state["clef"], self._random, previous)
        state["missed"] = False
        self._loading = True
        self.staff.load(lessons_engine.given_lines(self.exercise))
        self._loading = False
        self.staff.highlight = None
        self.staff.redraw()
        colours = self.colours
        for other in self.option_buttons.values():
            other.configure(state="normal", text_color=colours["text"],
                            border_color=colours["border"])
        self._wipe(self.feedback)
        state["started"] = time.monotonic()

    def _leave_practice(self) -> None:
        self._render_exercise()

    # -- el renglón de estado -----------------------------------------------

    def _status(self, text: str, warn: bool = False) -> None:
        try:
            if not self.status.winfo_manager():
                return
            self.status.configure(
                text=text, text_color=(self.colours["error"] if warn
                                       else self.colours["muted"]))
        except (tk.TclError, AttributeError):
            pass

    def _save_draft(self) -> None:
        if self.staff is not None and \
                self.exercise.kind in lessons_engine.WRITTEN:
            self.memory["drafts"][self.exercise.key] = self.staff.lines()
