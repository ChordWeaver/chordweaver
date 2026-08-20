# -*- coding: utf-8 -*-
"""
Compila con Cython los tres módulos calientes del motor.

    python build_engine.py            # compila
    python build_engine.py --clean    # borra lo compilado y vuelve a Python

Qué compila y por qué: son los que la búsqueda pisa millones de veces por
corrida. `fitness.py` es el evaluador, `style.py` son las reglas que el
evaluador llama una por acorde y por transición, `theory.py` está debajo de
los dos, y `ga.py` es la búsqueda misma --- cruzar, mutar y sembrar ---, con
`voicing.py` y `harmony.py`, que es a donde baja cuando arma un acorde.

**Los `.py` no se tocan.** Se compilan tal como están --- Cython los acepta
como Python válido --- así que el motor sigue corriendo sin compilador, sin
Cython instalado y sin ninguna dependencia, exactamente como antes. Lo único
que cambia es que si el `.pyd` está al lado del `.py`, Python lo prefiere:
`from .fitness import evaluate` se lo lleva sin que nadie tenga que
preguntar. Borrar los `.pyd` deja el programa andando igual, más lento.

Por eso mismo no es un paso obligatorio del build: quien no tenga MSVC
instalado corre `pyinstaller ChordWeaver.spec` y le sale un ejecutable que
funciona.
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

#: Los módulos que se compilan, en orden de cuánto los pisa la búsqueda.
#:
#: `ga.py` entró después que los otros y por una medición concreta: en el
#: Generador a 32 compases el evaluador no es el cuello ---está compilado y
#: además repartido entre ocho procesos--- y el 67% del tiempo se lo llevaba
#: `_mutate`, que vive acá. `voicing` y `harmony` van con él porque son a
#: donde `_sample_slot` y el juicio de la progresión bajan.
MODULES = ["fitness", "style", "theory", "ga", "voicing", "harmony"]

#: Dónde van los `.c` y los objetos intermedios. No son del usuario ni del
#: repositorio: son basura de compilación.
BUILD_DIR = os.path.join(HERE, "build", "cython")


def sources():
    return [os.path.join(HERE, "engine", f"{name}.py") for name in MODULES]


def compiled():
    """Todo lo que la compilación deja en `engine/`."""
    found = []
    for name in MODULES:
        for suffix in (".pyd", ".so", ".c"):
            path = os.path.join(HERE, "engine", name + suffix)
            if os.path.exists(path):
                found.append(path)
        # `fitness.cp314-win_amd64.pyd` y sus hermanos por versión.
        folder = os.path.join(HERE, "engine")
        for entry in os.listdir(folder):
            if entry.startswith(name + ".") and entry.endswith((".pyd", ".so")):
                path = os.path.join(folder, entry)
                if path not in found:
                    found.append(path)
    return found


def clean():
    for path in compiled():
        os.remove(path)
        print("borrado", os.path.relpath(path, HERE))
    if os.path.isdir(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    parent = os.path.dirname(BUILD_DIR)
    if os.path.isdir(parent) and not os.listdir(parent):
        os.rmdir(parent)
    print("el motor vuelve a correr en Python puro")


def _make_vswhere_findable() -> None:
    """
    Poner el `vswhere.exe` de Visual Studio en el PATH antes de compilar.

    Sin esto la compilación falla con "Unable to find a compatible Visual
    Studio installation" **teniendo MSVC instalado y andando**, y el mensaje
    no tiene nada que ver con la causa. Lo que pasa es esto: setuptools
    arranca `vcvarsall.bat` con `cmd /u`, o sea pidiendo la salida en UTF-16,
    y le lee el entorno de ahí. Si `vswhere.exe` no está en el PATH,
    `vcvarsall.bat` no lo encuentra y el **shell** escribe su "no se reconoce
    como un comando" en ANSI --- un byte por letra --- antes de que empiece
    la salida UTF-16. Son 102 bytes impares adelante, así que el UTF-16 queda
    corrido medio carácter y **todo** el volcado del entorno se decodifica
    como basura: ni una línea `CLAVE=valor` sobrevive, setuptools recibe un
    entorno vacío y concluye que no hay Visual Studio.

    Un error de codificación disfrazado de instalación faltante. Alcanza con
    que el aviso no exista.
    """
    if os.name != "nt":
        return
    root = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")
    if not root:
        return
    installer = os.path.join(root, "Microsoft Visual Studio", "Installer")
    if os.path.isfile(os.path.join(installer, "vswhere.exe")):
        os.environ["PATH"] = installer + os.pathsep + os.environ.get("PATH", "")


def build():
    _make_vswhere_findable()
    from Cython.Build import cythonize
    from setuptools import setup

    modules = cythonize(
        sources(),
        build_dir=BUILD_DIR,
        language_level=3,
        compiler_directives={
            # Las anotaciones de estos archivos son documentación para quien
            # lee, escritas contra `typing` y no contra Cython: `Sequence[int]`,
            # `Optional[ChordContext]`. Dejar que Cython las tome como tipos
            # cambiaría la semántica de un archivo que nadie escribió pensando
            # en eso, y este archivo justamente promete no cambiar ninguna.
            "annotation_typing": False,
            # El motor no depende de que un índice fuera de rango explote, pero
            # tampoco hay ninguno: se apagan los chequeos que el intérprete hace
            # y que acá siempre pasan.
            "boundscheck": False,
            "wraparound": True,      # los índices negativos SÍ se usan (p[-1])
            "cdivision": False,      # la división tiene que seguir siendo la de Python
        },
    )
    setup(
        name="chordweaver-engine",
        ext_modules=modules,
        script_args=["build_ext", "--inplace",
                     "--build-temp", BUILD_DIR,
                     # Sin esto setuptools se arma un `build/lib.win-amd64-...`
                     # en la raíz del proyecto, al lado de `app.py`. Todo lo
                     # intermedio va junto y se borra de una con `--clean`.
                     "--build-lib", os.path.join(BUILD_DIR, "lib")],
    )


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    else:
        build()
