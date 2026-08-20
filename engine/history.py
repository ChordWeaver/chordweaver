# -*- coding: utf-8 -*-
"""
Portable storage: where files go, and the history of recent productions.

Portability rule
----------------
Everything the application needs lives next to the executable. When frozen by
PyInstaller ``sys.executable`` points at the .exe, so the base directory is
the folder the user unzipped; when running from source we fall back to the
project root. Nothing is ever written to the user's home directory or to a
system location unless they explicitly pick one in the save dialog.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

#: How many productions are remembered.
HISTORY_LIMIT = 10

_HISTORY_FILENAME = "history.json"
_OUTPUT_DIRNAME = "output"


#: Variable de entorno que muda TODOS los datos a otra carpeta.
#:
#: Los seis archivos del usuario --- historial, logros, sendero, huevos,
#: visitas y preferencias --- y la carpeta `output/` cuelgan de
#: :func:`base_directory`, así que moverla los mueve a todos de una vez.
#:
#: Existe por una razón concreta: cada script de prueba que abre la ventana
#: tiene que acordarse de reapuntar seis rutas, y alcanza con que una se
#: olvide para que una corrida de prueba quede anotada en el historial de
#: verdad --- que guarda las diez últimas --- o para que un logro que el
#: usuario no consiguió aparezca conseguido. Reapuntar cada ruta por
#: separado es una lista que hay que mantener; mover la raíz es una sola
#: cosa y **no se puede olvidar desde adentro del proceso**.
#:
#: Es la hermana de `CHORDWEAVER_STORY_DELAY`, `CHORDWEAVER_VISIT` y
#: `CHORDWEAVER_VISION`: todas existen para poder probar sin romper nada.
SANDBOX_VARIABLE = "CHORDWEAVER_DATA_DIR"


def base_directory() -> str:
    """
    Folder that holds the application and all of its data.

    Frozen builds report the directory of the executable; source runs report
    the repository root (one level above this package). ``CHORDWEAVER_DATA_DIR``
    gana sobre las dos: ver :data:`SANDBOX_VARIABLE`.
    """
    sandbox = os.environ.get(SANDBOX_VARIABLE, "").strip()
    if sandbox:
        if not os.path.isdir(sandbox):
            try:
                os.makedirs(sandbox, exist_ok=True)
            except OSError:
                # Una carpeta de pruebas que no se puede crear no es motivo
                # para que el programa no arranque: se vuelve al lugar de
                # siempre, que es donde el usuario espera sus datos.
                return _installed_directory()
        return sandbox
    return _installed_directory()


def program_directory() -> str:
    """
    Donde vive el programa, **sin** mirar la variable de pruebas.

    Es la raíz de lo que el programa se trae puesto y no le pertenece al
    usuario: hoy, los recortes de `assets/`. `base_directory()` no sirve para
    eso porque `CHORDWEAVER_DATA_DIR` la mueve, y esa variable existe para
    mandar *los datos del usuario* a otro lado --- historial, logros,
    sendero, `output/` ---, no para mudar el arte del programa. Buscando los
    PNG ahí, cualquiera que la usara se quedaba sin personajes: las escenas
    se jugaban enteras y con los diálogos puestos, pero **vacías**, y sin un
    solo error --- `load_pose` devuelve `None` cuando el archivo no está, que
    es lo correcto para una pose que falta y lo peor posible para todas.
    """
    if getattr(sys, "frozen", False):
        # `sys._MEIPASS` y NO la carpeta del ejecutable. PyInstaller 6 dejó de
        # poner los `datas` al lado del .exe y los manda a `_internal/`, que es
        # justamente lo que apunta esta variable. Buscándolos al lado del .exe
        # el programa empaquetado se quedaba sin un solo personaje --- y en
        # silencio, porque una pose que no está devuelve `None`. Desde el
        # fuente no hay `_MEIPASS` y vale la raíz del repositorio, como antes.
        bundle = getattr(sys, "_MEIPASS", "")
        if bundle:
            return bundle
    return _installed_directory()


def _installed_directory() -> str:
    """Donde vive el programa: al lado del .exe, o la raíz del repositorio."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_output_directory() -> str:
    """Default place for generated scores: ``<base>/output``, created on demand."""
    path = os.path.join(base_directory(), _OUTPUT_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


#: Cómo queda anotado un compás de silencio en el historial. Es texto y no
#: el glifo, para que un archivo guardado se pueda leer en cualquier consola
#: y para que la pantalla decida cómo dibujarlo.
REST_LABEL = "(silencio)"


def history_path() -> str:
    return os.path.join(base_directory(), _HISTORY_FILENAME)


@dataclass
class ProductionRecord:
    """One remembered run: its parameters and the files it produced.

    The chord list is stored too -- it is only a handful of short strings, so
    the "that would be too much" worry does not really apply, and being able
    to reload a past progression is worth far more than the bytes it costs.
    """

    timestamp: str
    title: str
    genre: str
    voice_keys: List[str]
    bar_count: int
    time_signature: str
    #: Con cuál de los tres modos se hizo (`manual`, `harmonise`, `random`).
    #: Lleva valor por defecto porque las entradas escritas antes de que este
    #: campo existiera no lo traen, y `load_history` las construye por
    #: nombre: sin el default se descartarían enteras.
    mode: str = ""
    chord_symbols: List[str] = field(default_factory=list)
    durations: List[float] = field(default_factory=list)
    switches: Dict[str, Any] = field(default_factory=dict)
    ga_settings: Dict[str, Any] = field(default_factory=dict)
    solution_costs: List[float] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    #: Enough to redraw the result: the voice names, what each chord was
    #: called, and the pitches of every solution. Stored because a history
    #: that only lists parameters cannot show you what you made -- and a run
    #: is worth remembering whether or not it was saved to disk.
    voice_names: List[str] = field(default_factory=list)
    chord_labels: List[str] = field(default_factory=list)
    romans: List[str] = field(default_factory=list)
    #: solutions[i][slot][voice] -> MIDI pitch
    solutions: List[List[List[int]]] = field(default_factory=list)
    #: Las notas de adorno de cada solución, para poder volver a oírlas:
    #: ``ornaments[i]`` es una lista de ``[slot, voz, altura, porción]``,
    #: con el índice de slot de la partitura --- el mismo de `solutions`.
    #: Va aparte y no metido en `solutions` porque un adorno no es un acorde
    #: más: parte en dos el que ya está, y la pantalla de detalle muestra una
    #: columna por acorde escrito. Lleva default porque las entradas viejas
    #: no lo traen y `load_history` las construye por nombre.
    ornaments: List[List[List[float]]] = field(default_factory=list)

    @classmethod
    def create(cls, **kwargs) -> "ProductionRecord":
        kwargs.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))
        return cls(**kwargs)

    #: Nombre visible de cada estilo. Vive acá y no en la interfaz porque el
    #: historial es lo único que lee el archivo guardado, donde el estilo
    #: figura por su clave.
    GENRE_LABELS = {"classical": "Barroco", "chorale": "Coral",
                    "gregorian": "Gregoriano", "jazz": "Jazz"}
    MODE_LABELS = {"manual": "Organizador", "harmonise": "Armonizador",
                   "random": "Generador"}

    @property
    def genre_label(self) -> str:
        return self.GENRE_LABELS.get(self.genre, self.genre or "-")

    @property
    def mode_label(self) -> str:
        return self.MODE_LABELS.get(self.mode, "")

    @property
    def when(self) -> str:
        """
        Cuándo fue, escrito como lo diría alguien.

        Un sello ISO es exacto y no dice nada: en una lista de diez
        corridas hechas casi todas el mismo día, lo único que se busca es
        cuál es la de recién.
        """
        try:
            moment = datetime.fromisoformat(self.timestamp)
        except (ValueError, TypeError):
            return self.timestamp
        today = datetime.now().date()
        days = (today - moment.date()).days
        clock = moment.strftime("%H:%M")
        if days == 0:
            return f"hoy {clock}"
        if days == 1:
            return f"ayer {clock}"
        months = ("ene", "feb", "mar", "abr", "may", "jun",
                  "jul", "ago", "sep", "oct", "nov", "dic")
        return f"{moment.day} {months[moment.month - 1]} {clock}"

    @property
    def display_name(self) -> str:
        pieces = [p for p in (self.mode_label, self.genre_label) if p]
        return f"{self.when}  ·  {'  ·  '.join(pieces)}"


def load_history(path: Optional[str] = None) -> List[ProductionRecord]:
    """Read the history file, tolerating absence or corruption."""
    target = path or history_path()
    if not os.path.exists(target):
        return []
    try:
        with open(target, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (json.JSONDecodeError, OSError):
        # A damaged history must never stop the application from starting.
        return []

    records: List[ProductionRecord] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            records.append(ProductionRecord(**item))
        except TypeError:
            continue          # skip entries written by an older version
    return records


def save_history(records: List[ProductionRecord], path: Optional[str] = None) -> None:
    """Persist history, keeping only the newest ``HISTORY_LIMIT`` entries."""
    target = path or history_path()
    trimmed = records[:HISTORY_LIMIT]
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump([asdict(r) for r in trimmed], handle, indent=2, ensure_ascii=False)
    except OSError:
        pass                  # a read-only folder should not crash a run


def add_record(record: ProductionRecord, path: Optional[str] = None) -> List[ProductionRecord]:
    """Prepend a record to the history and save it. Returns the new list."""
    records = load_history(path)
    records.insert(0, record)
    records = records[:HISTORY_LIMIT]
    save_history(records, path)
    return records


def unique_basename(directory: str, stem: str) -> str:
    """
    Return a path stem inside ``directory`` that does not collide.

    Exports write several files from one stem (``.musicxml`` and ``.mid``),
    so uniqueness is checked against the stem rather than a full filename.
    """
    safe = "".join(c for c in stem if c.isalnum() or c in " -_").strip() or "score"
    candidate = os.path.join(directory, safe)
    counter = 2
    while os.path.exists(f"{candidate}.musicxml") or os.path.exists(f"{candidate}.mid"):
        candidate = os.path.join(directory, f"{safe} ({counter})")
        counter += 1
    return candidate


# ---------------------------------------------------------------------------
# Settings that survive a restart
# ---------------------------------------------------------------------------

_SETTINGS_FILENAME = "settings.json"

#: What a fresh installation starts from.
DEFAULT_SETTINGS: Dict[str, Any] = {
    "population_size": 200,
    "generations": 300,
    "elitism": 2,
    "tournament_size": 3,
    "mutation_rate": 0.12,
    "crossover_rate": 0.85,
    # 0,4 y no 0,5: es el valor de `GAConfig`, que es contra el que están
    # calibrados los pesos y con el que corren el CLI, los tests y
    # `audit.py`. Estuvo en 0,5 acá, así que la interfaz ---que lee estas
    # preferencias antes que el default del campo--- venía cruzando con
    # una mezcla distinta de la del motor, y "Restaurar valores por
    # defecto" dejaba 0,4: los dos caminos daban números distintos.
    "uniform_crossover_share": 0.4,
    "font_scale": 1.0,
    "raise_cadence_odds": False,
    "appearance": "dark",
    #: Si el recorrido guiado ya se hizo (o se omitió). Arranca solo la
    #: primera vez que se abre el programa.
    "tutorial_seen": False,
    #: Qué anotaciones del libro de teoría ya se leyeron, para poder marcar
    #: las nuevas. Son claves de logro; la lista crece sola.
    "book_seen": [],
}


def settings_path() -> str:
    return os.path.join(base_directory(), _SETTINGS_FILENAME)


def load_settings(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Read the stored preferences, falling back to the defaults.

    Anything missing or unreadable is filled in from ``DEFAULT_SETTINGS``, so
    a truncated or hand-edited file degrades to sane values instead of
    stopping the program from starting.
    """
    target = path or settings_path()
    values = dict(DEFAULT_SETTINGS)
    if not os.path.exists(target):
        return values
    try:
        with open(target, "r", encoding="utf-8") as handle:
            stored = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return values
    if isinstance(stored, dict):
        for key, value in stored.items():
            if key in DEFAULT_SETTINGS:
                values[key] = value
    return values


def save_settings(values: Dict[str, Any], path: Optional[str] = None) -> None:
    """Persist preferences next to the program."""
    target = path or settings_path()
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(values, handle, indent=2, ensure_ascii=False)
    except OSError:
        pass          # a read-only folder must not break the run
