# -*- coding: utf-8 -*-
"""
Las visitas: quién se aparece, cuándo, qué dice y qué deja escrito.

Es el mismo tipo de módulo que ``story.py`` y ``eggs.py`` --- guion, estado y
nada más ---, y por las mismas razones vive aparte de los dos. Una visita no
es un sendero: no se elige, no tiene tramos y no se puede abandonar a la
mitad. Y no es un huevo de pascua: se anuncia, deja una anotación en el libro
y el programa dice exactamente qué hay que hacer para que ocurra --- salvo
una, que es justamente la que no.

Quiénes son
-----------
* **Bach**, a las cinco partituras barrocas, y otra vez la primera vez que se
  usa el modo coral. Felicita y explica.
* **Gregorio**, a las cinco partituras gregorianas. Felicita y explica el
  organum, que es de donde salió el pentagrama entero.
* **La entidad**, al conseguir el cien por ciento de los logros. No felicita:
  mira, no entiende, y avisa de algo que todavía no pasó.
* **La visión** --- el guitarrista del cruce de caminos --- que puede ocurrir
  al abrir el programa, una vez en la vida y con una probabilidad de una en
  cinco. No habla. Es la única que no se puede provocar.

Dónde queda el estado
---------------------
En ``visitors.json``, al lado de ``history.json``, ``achievements.json``,
``story.json`` y ``eggs.json``. Cuántas partituras van de cada género, qué
visitas ya ocurrieron y si la visión ya se vio: nada de eso es una
preferencia (``settings.json`` es una lista blanca), ni un logro, ni un
sendero a medio andar.

Las llaves del libro
--------------------
Casi cada visita abre un apartado del capítulo de las visitas. La llave es
``visit_<clave>``, y quien pregunta --- ``app.py`` --- la contesta contra
este registro igual que contesta las otras contra los logros o contra el
sendero. Desde adentro del libro no hay ninguna diferencia: una llave es una
cadena que alguien sabe contestar.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from . import history
from .story import Line, NARRATOR

_FILENAME = "visitors.json"

#: Los que vienen de visita. Son claves de ``cinematic.POSES``, igual que los
#: del sendero.
BACH = "bach"
GREGORY = "gregory"
WATCHER = "watcher"
ROBERT = "robert"

#: Cuántas partituras de un género hacen falta para que aparezca su maestro.
#: Cada corrida terminada cuenta como una.
NEEDED = 5

#: Las claves de género que se cuentan. ``classical`` es el barroco --- el
#: nombre viejo del motor, que la interfaz ya no muestra --- y el modo coral
#: cuenta como barroco porque **es** barroco: es un switch adentro del
#: género, no un género aparte.
BAROQUE = "classical"
GREGORIAN = "gregorian"
COUNTED: Tuple[str, ...] = (BAROQUE, GREGORIAN)

#: Prefijo de las llaves del libro.
BOOK_PREFIX = "visit_"

#: Con qué probabilidad ocurre la visión al abrir el programa.
VISION_ODDS = 0.20

#: El cuarto objeto. Los tres primeros los entregan los senderos; éste lo deja
#: la entidad, y es el único que no se sabe de quién es.
KEEPSAKE = "Una partitura quemada"
KEEPSAKE_ICON = "🔥"


@dataclass(frozen=True)
class Visit:
    """Una aparición: quién, qué dice y cómo se pone en escena."""

    key: str
    speaker: str
    lines: Tuple[Line, ...]
    #: La línea que se lee sobre el negro antes de que la escena se abra.
    dream: str = ""
    #: El rótulo de arriba de todo, mientras dura la escena.
    title: str = ""
    #: El nombre que aparece en el cartelito cuando la línea lo pide con el
    #: gesto ``reveal``. Hasta ahí dice ``? ? ?``, igual que en el sendero:
    #: quién es se descubre, no se anuncia.
    name: str = ""
    keepsake: Tuple[str, str] = ("", "")


# ---------------------------------------------------------------------------
# Bach
# ---------------------------------------------------------------------------
#
# Habla como un artesano, no como un genio: para él la música es un oficio
# que se aprende, se practica y se entrega a tiempo. Las dos citas son suyas
# de verdad, y las dos dicen exactamente eso.

_BACH_BAROQUE: Tuple[Line, ...] = (
    Line(NARRATOR, "Alguien aplaude, despacio, tres veces."),
    Line(BACH, "Cinco. Ya llevás cinco.", pose="normal"),
    Line(BACH, "No es poco. Casi nadie llega a la quinta: la primera la hace "
               "cualquiera, la segunda se hace por curiosidad, y de ahí en "
               "adelante ya hay que quererlo.", cue="reveal"),
    Line(BACH, "Déjame decirte qué es lo que estuviste haciendo, porque "
               "seguramente nadie te lo dijo.", pose="gesto"),
    Line(BACH, "En mi tiempo la música no se escribía en acordes. Se "
               "escribía en voces. Cuatro personas, cuatro caminos, cada uno "
               "con su propio sentido de arriba abajo.", pose="normal"),
    Line(BACH, "El acorde es lo que se oye cuando los cuatro caminos pasan "
               "por el mismo punto. Es una consecuencia, no un ingrediente.",
         pose="gesto"),
    Line(BACH, "Por eso el bajo importa tanto. Abajo de todo va una línea "
               "sola con unos números escritos debajo --- nosotros la "
               "llamábamos bajo continuo --- y de esos números sale todo lo "
               "demás.", pose="normal"),
    Line(BACH, "Un teclista leía ese bajo y completaba la armonía en el "
               "momento, sin que nadie se la escribiera. Se improvisaba mucho "
               "más de lo que creen.", pose="gesto"),
    Line(BACH, "Y lo otro: cada voz tiene que poder cantarse sola. Si una "
               "línea sólo tiene sentido cuando suenan las otras tres, esa "
               "línea está mal escrita, por más que el acorde cierre.",
         pose="normal"),
    Line(BACH, "Eso es todo el oficio. No hay ningún secreto y no hay ningún "
               "don.", pose="gesto"),
    Line(BACH, "«No hay nada notable en ello. Sólo hay que tocar la tecla "
               "correcta en el momento adecuado, y el instrumento se toca "
               "solo.»", pose="normal"),
    Line(BACH, "Me lo dijeron toda la vida como si fuera modestia. Nunca lo "
               "fue. Es la instrucción entera.", pose="gesto"),
    Line(NARRATOR, "Deja el rollo de papel sobre la mesa. Cuando volvés a "
                   "mirar, no está ninguno de los dos."),
)

_BACH_CHORALE: Tuple[Line, ...] = (
    Line(NARRATOR, "Un solo golpe en la mesa, como quien pide silencio antes "
                   "de que entre el coro."),
    Line(BACH, "Ah. Pusiste el modo coral.", pose="normal", cue="reveal"),
    Line(BACH, "Escribí trescientos y pico de ésos. Vale la pena que sepas "
               "qué los diferencia de todo lo demás que hiciste hasta "
               "ahora.", pose="gesto"),
    Line(BACH, "Un coral no es una pieza mía. La melodía de arriba es un "
               "himno que la congregación entera ya se sabía de memoria: yo "
               "no la inventé, la recibí.", pose="normal"),
    Line(BACH, "Lo que se escribe es lo que va debajo. Tres voces más, "
               "sosteniendo una melodía que no es de uno.", pose="gesto"),
    Line(BACH, "Primero: las cuatro voces se mueven juntas. Una sílaba, un "
               "acorde. En el resto del barroco cada voz corre por su lado; "
               "acá van todas al mismo paso, porque atrás hay gente cantando "
               "y hay que dejarla entrar.", pose="normal"),
    Line(BACH, "Segundo: se canta, no se toca. Nada de saltos imposibles, "
               "nada de notas fuera del alcance de una garganta común, y "
               "cada voz tiene que poder respirar donde termina la frase.",
         pose="gesto"),
    Line(BACH, "Tercero: las frases se cortan. Al final de cada verso hay un "
               "calderón --- una pausa larga --- y ahí se arma una cadencia "
               "de verdad. Un coral son ocho frases chiquitas, no una frase "
               "larga.", pose="normal"),
    Line(BACH, "Y cuarto: las reglas se aprietan. Nada de quintas y octavas "
               "paralelas, nada de voces cruzadas, nada de huecos enormes "
               "entre una voz y la de al lado.", pose="gesto"),
    Line(BACH, "No es rigor por rigor. Es que cuatro personas que no son "
               "músicos tienen que poder sostener eso de memoria, un domingo "
               "a la mañana, sin ensayar.", pose="normal"),
    Line(BACH, "«El fin último de toda música no debe ser otro que la gloria "
               "de Dios y la recreación del espíritu.»", pose="gesto"),
    Line(BACH, "Lo escribí en el margen de un cuaderno de ejercicios, no en "
               "una carta importante. Al lado de un ejercicio, que es donde "
               "corresponde.", pose="normal"),
    Line(NARRATOR, "Se va sin darse vuelta, como quien tiene que entregar "
                   "una cantata el domingo."),
)


# ---------------------------------------------------------------------------
# Gregorio
# ---------------------------------------------------------------------------
#
# Le pusieron su nombre a un canto que no escribió, y lo sabe. Explica el
# organum, que es de donde salió todo lo que el programa hace: la primera vez
# que alguien anotó dos voces a la vez.

_GREGORY: Tuple[Line, ...] = (
    Line(NARRATOR, "El aire huele a piedra fría. Muy lejos, alguien sostiene "
                   "una nota sola."),
    Line(GREGORY, "Cinco veces cantaste a una sola voz. Cinco.",
         pose="normal", cue="reveal"),
    Line(GREGORY, "Poca gente aguanta cinco. El canto llano no tiene con qué "
                  "entretener: no hay acordes, no hay compás, no hay nada "
                  "más que la línea.", pose="normal"),
    Line(GREGORY, "Antes de que sigas, una aclaración que me debo hace mil "
                  "cuatrocientos años: ese canto no lo escribí yo.",
         pose="canto"),
    Line(GREGORY, "Me pusieron el nombre trescientos años después de "
                  "muerto, para que la colección tuviera un autor. Los "
                  "cantos eran de todos y de nadie.", pose="normal"),
    Line(GREGORY, "Lo que sí pasó en esos monasterios es lo que te quiero "
                  "contar. Se llama organum, y es el primer momento en que "
                  "dos voces suenan a la vez a propósito.", pose="canto"),
    Line(GREGORY, "Funciona así: uno canta el canto de siempre --- la vox "
                  "principalis, la voz principal --- y otro canta exactamente "
                  "lo mismo, nota por nota, pero cuatro o cinco escalones más "
                  "abajo. Ésa es la vox organalis.", pose="normal"),
    Line(GREGORY, "No es una segunda melodía. Es la misma melodía, corriendo "
                  "en paralelo, como una sombra.", pose="canto"),
    Line(GREGORY, "Por qué a esa distancia y no a otra: porque la cuarta y la "
                  "quinta eran los únicos intervalos que se consideraban "
                  "perfectos. Las terceras --- lo que hoy te suena dulce --- "
                  "eran disonancias.", pose="normal"),
    Line(GREGORY, "Todo lo que vino después es esto complicándose. Cuando la "
                  "sombra empezó a moverse por su cuenta en vez de seguir a "
                  "la voz, nació el contrapunto. Y de ahí, mil años más "
                  "tarde, sale lo que hace tu programa.", pose="canto"),
    Line(GREGORY, "De mí se recuerda una sola frase, y es sobre las "
                  "Escrituras: «es como un río llano y profundo, donde el "
                  "cordero camina y el elefante nada».", pose="normal"),
    Line(GREGORY, "Sirve igual para esto. Una línea sola, sin acordes: un "
                  "chico la canta el primer día. Y sin embargo llevo mil "
                  "cuatrocientos años oyendo discutir cómo se anota.",
         pose="canto"),
    Line(NARRATOR, "La nota lejana se apaga. Nadie la cortó: simplemente se "
                   "quedó sin aire."),
)


# ---------------------------------------------------------------------------
# La entidad
# ---------------------------------------------------------------------------
#
# No felicita, no explica y no enseña nada: es la única visita que no viene a
# dar una clase. Habla de algo que todavía no pasó y se va sin decir qué era,
# que es lo único que se puede hacer con un final que no existe.

_WATCHER: Tuple[Line, ...] = (
    Line(NARRATOR, "No entró. Estaba."),
    Line(WATCHER, "Te estuve mirando.", pose="normal"),
    Line(WATCHER, "Desde la primera partitura torcida. Desde la vez que "
                  "dejaste el programa abierto y te fuiste a hacer otra "
                  "cosa."),
    Line(WATCHER, "No entiendo cómo lo hiciste. Lo digo en serio: no lo "
                  "entiendo.", cue="shake"),
    Line(WATCHER, "He visto a mucha gente empezar. Casi todos se van en la "
                  "tercera pantalla. Vos no dejaste nada sin tocar."),
    Line(WATCHER, "Es impresionante. No tengo otra palabra, y no suelo "
                  "usarla."),
    Line(WATCHER, "Así que te voy a contar algo que no le conté a nadie."),
    Line(WATCHER, "Va a venir alguien. No sé cuándo. Alguien con más poder "
                  "del que hubo nunca sobre esto."),
    # Sin fogonazo. Hubo uno acá --- la pantalla entera en dorado --- y no
    # pintaba nada: lo que ella está diciendo no es que pasó algo, es que va a
    # pasar. Iluminar la escena para anunciar algo que todavía no ocurrió le
    # sacaba lo único que tiene, que es que no se ve.
    Line(WATCHER, "Y cuando llegue, la música va a cambiar para siempre. No "
                  "un género, no un estilo: toda."),
    Line(WATCHER, "Le dicen el faro. El que va a guiar a todos hacia una "
                  "nueva edad dorada."),
    Line(WATCHER, "Vos vas a estar ahí. Con todo lo que aprendiste acá, vas "
                  "a estar ahí."),
    Line(WATCHER, "Te dejo esto. No preguntes de quién es, porque no se "
                  "puede leer.", cue="item"),
    Line(NARRATOR, "Es una partitura quemada. Queda el pentagrama, alguna "
                   "cabeza de nota, y una firma que el fuego se comió justo "
                   "por la mitad."),
    Line(WATCHER, "Guardala. Alguna vez vas a saber qué decía."),
    Line(NARRATOR, "Y como no se lo vio llegar, tampoco se lo ve irse."),
)


# ---------------------------------------------------------------------------
# El catálogo
# ---------------------------------------------------------------------------

BACH_BAROQUE = "bach_baroque"
BACH_CHORALE = "bach_chorale"
GREGORY_CHANT = "gregory"
WATCHER_ALL = "watcher"
#: La visión no tiene diálogo --- el guitarrista no habla --- pero sí llave
#: de libro, que es lo único que deja.
VISION = "robert"

VISITS: Dict[str, Visit] = {
    BACH_BAROQUE: Visit(
        BACH_BAROQUE, BACH, _BACH_BAROQUE,
        dream="—  el quinto trabajo entregado  —",
        title="—  alguien vino a leer lo que escribiste  —",
        name="Johann Sebastian Bach"),
    BACH_CHORALE: Visit(
        BACH_CHORALE, BACH, _BACH_CHORALE,
        dream="—  cuatro voces y una congregación  —",
        title="—  alguien vino a leer lo que escribiste  —",
        name="Johann Sebastian Bach"),
    GREGORY_CHANT: Visit(
        GREGORY_CHANT, GREGORY, _GREGORY,
        dream="—  una sola línea, sin acordes debajo  —",
        title="—  alguien vino a escuchar  —",
        name="Gregorio I"),
    WATCHER_ALL: Visit(
        WATCHER_ALL, WATCHER, _WATCHER,
        dream="—  no queda nada por conseguir  —",
        title="",
        name="",
        keepsake=(KEEPSAKE_ICON, KEEPSAKE)),
}

#: En qué orden se cuentan cuando se disparan dos a la vez. Pasa de verdad:
#: la quinta partitura barroca puede ser además la primera coral.
ORDER: Tuple[str, ...] = (BACH_BAROQUE, BACH_CHORALE, GREGORY_CHANT,
                          WATCHER_ALL)

#: Las visitas que dejan algo escrito en el libro.
#:
#: La entidad **no** está: no explica nada. Viene a mirar, avisa de algo que
#: todavía no pasó y se va, y lo que deja son dos regalos --- la partitura
#: quemada y la lista de los huevos --- que no son una lección. Un apartado
#: con su profecía adentro sería el único del libro que no enseña nada.
WRITES: Tuple[str, ...] = (BACH_BAROQUE, BACH_CHORALE, GREGORY_CHANT, VISION)

#: Las llaves de libro de todo lo anterior.
BOOK_KEYS: Tuple[str, ...] = tuple(BOOK_PREFIX + key for key in WRITES)


def writes(key: str) -> bool:
    """¿Esta visita deja una anotación? La entidad no."""
    return key in WRITES


def book_key(key: str) -> str:
    """La llave de libro de una visita."""
    return BOOK_PREFIX + key


def visit_key(book_lock: str) -> str:
    """La visita que abre una llave de libro. Vacío si no es una de las nuestras."""
    if not book_lock.startswith(BOOK_PREFIX):
        return ""
    return book_lock[len(BOOK_PREFIX):]


#: Con qué variable de entorno se fuerza una visita al abrir el programa.
#: Es la hermana de ``CHORDWEAVER_STORY_DELAY`` y existe por el mismo motivo:
#: la entidad aparece una sola vez, al conseguir el cien por ciento de los
#: logros, y no hay forma sensata de mirar esa escena dos veces sin esto.
FORCE_VAR = "CHORDWEAVER_VISIT"

#: Y ésta fuerza la visión, que si no es una en cinco y una sola vez en la
#: vida. ``0`` la apaga aunque todavía no se haya visto.
VISION_VAR = "CHORDWEAVER_VISION"


def forced(environ=None) -> str:
    """
    Qué visita pidió la variable de entorno. Vacío si no pidió ninguna.

    Vale cualquier clave del catálogo: ``watcher``, ``bach_baroque``,
    ``bach_chorale`` o ``gregory``. Una clave que no exista se ignora en
    silencio --- es una herramienta de prueba, no una entrada del usuario.
    """
    source = os.environ if environ is None else environ
    key = str(source.get(FORCE_VAR, "")).strip()
    return key if key in VISITS else ""


def vision_forced(environ=None) -> Optional[bool]:
    """
    Lo que la variable de entorno dice sobre la visión.

    ``True`` la obliga, ``False`` la prohíbe y ``None`` deja decidir al
    sorteo de siempre.
    """
    source = os.environ if environ is None else environ
    raw = str(source.get(VISION_VAR, "")).strip().lower()
    if not raw:
        return None
    return raw not in ("0", "no", "off", "false")


def vision_due(seen: bool, roll: float, tutorial_done: bool) -> bool:
    """
    ¿Ocurre la visión en este arranque?

    ``roll`` se pasa desde afuera --- es ``random.random()`` en el programa
    --- para que la condición siga siendo una función pura y se pueda probar
    sin sortear nada. Una vez vista no vuelve a ocurrir nunca: es lo que la
    hace valer.

    ``tutorial_done`` es que el recorrido guiado se haya terminado u omitido.
    La primera vez que alguien abre el programa lo que tiene enfrente es el
    tutorial, y la visión no es una escena para interrumpir eso: llega antes
    de que haya visto un solo acorde y sin nada con qué leerla, y se gasta
    la única vez que ocurre. Va acá y no confiada al chequeo general de "¿es
    un momento tranquilo?" que hace la interfaz porque es una condición de
    la visión y no del momento, y porque es lo que deja no sintetizar sus
    cinco ruidos en el arranque donde no puede pasar. El parámetro no lleva
    valor por defecto a propósito: un default sería la vieja condición
    entrando en silencio si alguien se olvida de pasarlo.
    """
    return (not seen) and bool(tutorial_done) and 0.0 <= roll < VISION_ODDS


# ---------------------------------------------------------------------------
# Lo que este usuario lleva visto
# ---------------------------------------------------------------------------

def visitors_path() -> str:
    return os.path.join(history.base_directory(), _FILENAME)


class Ledger:
    """
    Cuántas partituras van, qué visitas ocurrieron y si la visión ya se vio.

    Misma regla que el registro de logros, el sendero y los huevos: se guarda
    sólo cuando algo cambió, y un archivo roto o de otra versión no puede
    impedir que el programa arranque.
    """

    def __init__(self, counts: Optional[Dict[str, int]] = None,
                 seen: Optional[Dict[str, str]] = None,
                 vision: str = "", keepsake: bool = False,
                 path: Optional[str] = None):
        #: clave de género -> partituras terminadas.
        self.counts: Dict[str, int] = {key: int(counts.get(key, 0))
                                       for key in COUNTED} if counts else {
            key: 0 for key in COUNTED}
        #: clave de visita -> marca de tiempo ISO.
        self.seen: Dict[str, str] = dict(seen or {})
        #: Cuándo ocurrió la visión. Vacío mientras no haya ocurrido.
        self.vision = str(vision or "")
        #: Si la partitura quemada ya está entregada.
        self.keepsake = bool(keepsake)
        self.path = path

    # -- persistencia -------------------------------------------------------

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Ledger":
        target = path or visitors_path()
        if not os.path.exists(target):
            return cls(path=path)
        try:
            with open(target, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return cls(path=path)
        if not isinstance(raw, dict):
            return cls(path=path)
        counts = raw.get("counts", {})
        if not isinstance(counts, dict):
            counts = {}
        clean_counts: Dict[str, int] = {}
        for key in COUNTED:
            try:
                clean_counts[key] = max(0, int(counts.get(key, 0)))
            except (TypeError, ValueError):
                clean_counts[key] = 0
        seen = raw.get("seen", {})
        if not isinstance(seen, dict):
            seen = {}
        clean_seen = {k: str(v) for k, v in seen.items() if k in VISITS}
        return cls(clean_counts, clean_seen, str(raw.get("vision", "")),
                   bool(raw.get("keepsake", False)), path=path)

    def save(self) -> None:
        target = self.path or visitors_path()
        try:
            with open(target, "w", encoding="utf-8") as handle:
                json.dump({"counts": self.counts, "seen": self.seen,
                           "vision": self.vision, "keepsake": self.keepsake},
                          handle, indent=2, ensure_ascii=False)
        except OSError:
            pass          # una carpeta de sólo lectura no puede romper nada

    # -- consultas ----------------------------------------------------------

    def saw(self, key: str) -> bool:
        return key in self.seen

    def count(self, genre_key: str) -> int:
        return self.counts.get(genre_key, 0)

    def knows(self, book_lock: str) -> bool:
        """¿Está escrito el apartado que abre esta llave?"""
        key = visit_key(book_lock)
        if not key:
            return False
        if key == VISION:
            return bool(self.vision)
        return self.saw(key)

    # -- lo que pasa ---------------------------------------------------------

    def record(self, genre_key: str, chorale: bool = False) -> List[str]:
        """
        Anotar una partitura terminada y devolver las visitas que dispara.

        Devuelve claves, no escenas: quién las dibuja es problema de la
        interfaz. Lo que sí decide acá es el orden, para que la quinta
        barroca que además es la primera coral traiga a Bach una sola vez y
        con las dos cosas para decir, en el orden en que hay que decirlas.

        **No marca nada como vista.** Una visita ocurre cuando la escena
        termina, no cuando se decide: si el programa se cerrara en el medio,
        el usuario perdería una escena que no llegó a ver.
        """
        if genre_key not in self.counts:
            # Un género que no cuenta --- el jazz --- no anota nada y no
            # dispara nada. Igual se guarda: no hay nada que guardar.
            return []
        self.counts[genre_key] = self.counts.get(genre_key, 0) + 1
        self.save()
        due: List[str] = []
        if (genre_key == BAROQUE and self.counts[BAROQUE] >= NEEDED
                and not self.saw(BACH_BAROQUE)):
            due.append(BACH_BAROQUE)
        if genre_key == BAROQUE and chorale and not self.saw(BACH_CHORALE):
            due.append(BACH_CHORALE)
        if (genre_key == GREGORIAN and self.counts[GREGORIAN] >= NEEDED
                and not self.saw(GREGORY_CHANT)):
            due.append(GREGORY_CHANT)
        order = {key: index for index, key in enumerate(ORDER)}
        return sorted(due, key=lambda key: order[key])

    def mark(self, key: str) -> bool:
        """Dar una visita por ocurrida. ``True`` sólo la primera vez."""
        if key not in VISITS or key in self.seen:
            return False
        self.seen[key] = datetime.now().isoformat(timespec="seconds")
        self.save()
        return True

    def mark_vision(self) -> bool:
        """Dar la visión por vista. No vuelve a ocurrir nunca."""
        if self.vision:
            return False
        self.vision = datetime.now().isoformat(timespec="seconds")
        self.save()
        return True

    def take_keepsake(self) -> bool:
        """Quedarse con la partitura quemada. ``True`` si acaba de entregarse."""
        if self.keepsake:
            return False
        self.keepsake = True
        self.save()
        return True

    def keepsakes(self) -> List[Tuple[str, str]]:
        """Los objetos que dejaron las visitas, listos para mostrar."""
        return [(KEEPSAKE_ICON, KEEPSAKE)] if self.keepsake else []


def lines_of(key: str) -> Sequence[Line]:
    """El diálogo de una visita, o vacío si no existe."""
    visit = VISITS.get(key)
    return visit.lines if visit is not None else ()
