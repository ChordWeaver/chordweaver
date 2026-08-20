# -*- coding: utf-8 -*-
"""
Drives the interface the way a person does.

Every check in here goes through the actual widgets -- clicking cards,
typing in entries, pressing Next -- because that is the only way to catch
the class of bug where the engine is right and the interface never asks it
the right question. Reading the engine directly proves nothing about what
the user sees.
"""

from __future__ import annotations

import os
import tempfile
import time
from typing import Dict, List, Optional

# ANTES de importar `app`, y antes de que exista ninguna ventana: mover la
# raíz de los datos manda los seis archivos del usuario y la carpeta
# `output/` a un descartable de una sola vez. Los reapuntes de más abajo
# siguen estando --- son la API con la que la aplicación se deja mover ---
# pero esto es lo que cubre a cualquier script que construya
# `ChordWeaverApp` a mano en vez de pasar por `Session`, que es exactamente
# como se escaparon un par de corridas de prueba al historial de verdad.
import os as _os
import tempfile as _tempfile

from engine import history as _history

_os.environ.setdefault(
    _history.SANDBOX_VARIABLE,
    _os.path.join(_tempfile.gettempdir(), "chordweaver-uitest-data"))

import app as A
from engine import visitors


class Session:
    """One run through the app, from the first screen to the results."""

    def __init__(self, geometry: str = "1180x860"):
        self.win = A.ChordWeaverApp()
        # El tutorial arranca solo la primera vez y taparía con su velo todo
        # lo que estas pruebas manejan. Se apaga sólo en memoria: la
        # preferencia guardada no se toca, así que el usuario lo sigue viendo
        # cuando le corresponde.
        self.win.settings["tutorial_seen"] = True
        if getattr(self.win, "tutorial", None) is not None:
            self.win.tutorial._clear()
            self.win.tutorial = None
        # Lo mismo con el modo historia: la figura aparece sola después de un
        # rato y su escena tapa la ventana entera, así que el arnés no podría
        # tocar nada. Se apaga sólo en memoria --- `story.json` no se toca ---
        # y quien quiera probar las cinemáticas lo hace pidiéndolas.
        # Se apaga el ofrecimiento con su propio interruptor. Antes se lo
        # apagaba poniendo `seen_offer` --- un dato del usuario --- y eso
        # dejó de apagar nada cuando `may_offer` pasó a preguntar sólo por
        # el sendero: la marca dice que la figura ya se apareció, no que no
        # tenga que volver.
        self.win.story_offers = False
        self.win.story.seen_offer = True
        # Y las visitas, por dos motivos distintos. Uno: la visión ocurre al
        # abrir la ventana una vez de cada cinco, así que sin apagarla una de
        # cada cinco corridas del arnés se encontraría con una escena tapando
        # todo y fallaría sin ninguna razón. Dos: el arnés genera decenas de
        # partituras seguidas, que es exactamente lo que hace aparecer a Bach
        # y a Gregorio.
        #
        # Se dan todas por vistas en memoria y el registro se manda a un
        # archivo descartable: los datos de verdad del usuario --- cuántas
        # partituras lleva hechas, a quién vio --- no los toca nadie.
        # Y el historial y los logros van a archivos descartables. El arnés
        # genera decenas de partituras seguidas y cada una se anota: como el
        # historial guarda sólo las diez últimas, diez corridas de prueba
        # bastaban para borrar el del usuario, y los logros que estas
        # corridas consiguen son logros que el usuario no consiguió.
        scratch = tempfile.gettempdir()
        self.win.history_path = os.path.join(scratch,
                                             "chordweaver-uitest-history.json")
        # Las preferencias se leen del archivo de verdad --- el arnés tiene
        # que correr con la configuración del usuario --- pero se escriben en
        # un descartable. Cualquier cosa que llame a `save_settings` (el panel
        # de configuración, el final del tutorial, marcar una anotación como
        # leída) las pisaba, y `book_seen` decide qué anotaciones le figuran
        # como nuevas al usuario.
        self.win.settings_path = os.path.join(
            scratch, "chordweaver-uitest-settings.json")
        self.win.achievements.path = os.path.join(
            scratch, "chordweaver-uitest-achievements.json")
        self.win.achievements.unlocked = {}
        self.win.eggs.path = os.path.join(scratch,
                                          "chordweaver-uitest-eggs.json")
        self.win.eggs.found = {}
        self.win.story.file_path = os.path.join(
            scratch, "chordweaver-uitest-story.json")
        self.win.visits.vision = "uitest"
        self.win.visits.seen = {key: "uitest" for key in visitors.VISITS}
        self.win.visits.path = os.path.join(tempfile.gettempdir(),
                                            "chordweaver-uitest-visitors.json")
        self.win.geometry(geometry)
        self.win.update()

    # -- navigation ---------------------------------------------------------

    def next(self) -> bool:
        moved = self.win._go_next()
        self.win.update()
        return moved

    def screen(self) -> str:
        return self.win.screen_titles[self.win.index]

    def home(self) -> None:
        self.win._go_home()
        self.win.update()

    def close(self) -> None:
        try:
            self.win.destroy()
        except Exception:                                   # noqa: BLE001
            pass

    # -- setup --------------------------------------------------------------

    def mode(self, key: str) -> "Session":
        self.win._select_mode(key)
        self.win.update()
        return self

    def genre(self, key: str) -> "Session":
        self.win._select_genre(key)
        self.win.update()
        return self

    def voices(self, keys) -> "Session":
        for name, var in self.win.voice_check_vars.items():
            var.set(name in keys)
        self.win.update()
        return self

    def bars(self, count: int) -> "Session":
        self.win.bar_count_entry.delete(0, "end")
        self.win.bar_count_entry.insert(0, str(count))
        self.win._rebuild_bar_rows()
        self.win.update()
        return self

    def chords(self, symbols: List[str]) -> "Session":
        position = 0
        for row in self.win.chord_rows:
            for cell in row["entries"]:
                if position < len(symbols):
                    cell["entry"].delete(0, "end")
                    cell["entry"].insert(0, symbols[position])
                    self.win._validate_chord(cell)
                position += 1
        self.win.update()
        return self

    def key(self, tonic: str, mode_label: str) -> "Session":
        self.win.tonic_menu.set(tonic)
        self.win.mode_menu.set(mode_label)
        self.win.update()
        return self

    def search(self, population: int = 70, generations: int = 30) -> "Session":
        """Set the search size and make the app read it.

        Writing the variables is not enough: the app only picks them up when
        the parameters screen is committed, so the commit is forced here.
        Otherwise every timing measured through this harness is really the
        default 200x300 run.
        """
        self.win.ga_vars["population_size"].set(str(population))
        self.win.ga_vars["generations"].set(str(generations))
        self.win._read_ga_config()
        self.win.update()
        return self

    # -- running ------------------------------------------------------------

    def generate(self, timeout: float = 120.0):
        """Press Generate and wait for a real result."""
        self.next()
        started = time.time()
        while self.win.outcome is None and time.time() - started < timeout:
            self.win.update()
            time.sleep(0.03)
        self.win.update()
        self.win.update_idletasks()
        return self.win.outcome

    def run(self, screens_before_generate: int = 5, **kwargs):
        """Walk the whole carousel and generate."""
        for _ in range(screens_before_generate):
            self.next()
        return self.generate(**kwargs)

    # -- reading what is on screen -----------------------------------------

    def labels(self, root=None) -> List[str]:
        """Every visible label, read from the live widget tree."""
        found: List[str] = []

        def walk(widget) -> None:
            try:
                children = widget.winfo_children()
            except Exception:                               # noqa: BLE001
                return
            for child in children:
                if isinstance(child, A.ctk.CTkLabel):
                    try:
                        text = child.cget("text")
                        if text:
                            found.append(text)
                    except Exception:                       # noqa: BLE001
                        pass
                walk(child)

        walk(root if root is not None else self.win.body)
        return found

    def banners(self) -> List[str]:
        return [t for t in self.labels() if t.startswith("★")]

    def chord_headers(self) -> List[str]:
        """The chord symbols shown above each column, per option block."""
        outcome = self.win.outcome
        if outcome is None or not outcome.succeeded:
            return []
        texts = self.labels()
        # Headers are short and start with a note letter.
        return [t for t in texts
                if t and t[0] in "ABCDEFG" and len(t) < 16]

    def tinted(self) -> int:
        """How many chord headers are painted with the flourish colour."""
        count = 0

        def walk(widget) -> None:
            nonlocal count
            try:
                children = widget.winfo_children()
            except Exception:                               # noqa: BLE001
                return
            for child in children:
                try:
                    if (isinstance(child, A.ctk.CTkFrame)
                            and child.cget("fg_color") == A.SET_PIECE_TINT):
                        count += 1
                except Exception:                           # noqa: BLE001
                    pass
                walk(child)

        walk(self.win.body)
        return count


def solution_chords(outcome, index: int = 0) -> List[List[int]]:
    return [list(chord) for chord in outcome.result.solutions[index].slots]


def chord_symbols(outcome, index: int = 0) -> List[str]:
    """The symbol each slot carries for a given solution."""
    solution = outcome.result.solutions[index]
    out = []
    for column, slot in enumerate(outcome.spec.slots):
        if slot.options and column < len(solution.choices):
            choice = min(solution.choices[column], len(slot.options) - 1)
            out.append(slot.options[choice].requirement.chord.symbol)
        else:
            out.append(slot.symbol)
    return out


def romans(outcome, index: int = 0) -> List[str]:
    solution = outcome.result.solutions[index]
    out = []
    for column, slot in enumerate(outcome.spec.slots):
        if slot.options and column < len(solution.choices):
            choice = min(solution.choices[column], len(slot.options) - 1)
            harmony_option = slot.options[choice].harmony
            out.append(harmony_option.roman if harmony_option else "")
        else:
            out.append("")
    return out
