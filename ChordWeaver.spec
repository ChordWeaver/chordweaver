# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build script for a portable ChordWeaver folder.

Build with:      pyinstaller ChordWeaver.spec
Result:          dist/ChordWeaver/  (a self-contained folder -- copy it anywhere)

A one-folder build is used rather than --onefile on purpose: the application
is supposed to keep its history and output next to the executable, and a
one-file build unpacks to a temporary directory where nothing would persist.

Sobre `engine/*.pyd`: si antes se corrió `python build_engine.py`, seis
módulos del motor están compilados con Cython y PyInstaller se los lleva
solos --- los encuentra por los mismos `hiddenimports` de siempre, porque
`engine.fitness` resuelve al `.pyd` antes que al `.py`. **No hace falta
tocar nada acá para que entren, y no hace falta compilarlos para que el
build funcione**: sin ellos se empaquetan los `.py` y sale un ejecutable
idéntico, más lento. Lo único que no hay que hacer es empaquetar un `.pyd`
compilado para otra versión de Python que la del build.
"""

import os

block_cipher = None

# Absolute path to this spec's folder, so the build works no matter which
# directory PyInstaller is launched from.
PROJECT_DIR = os.path.abspath(os.getcwd())

a = Analysis(
    ['app.py'],
    pathex=[PROJECT_DIR],
    binaries=[],
    # Todo lo que el programa trae puesto: los recortes del modo historia,
    # la fuente musical Bravura y la partitura de ejemplo del analizador. Va
    # como carpeta entera: agregar una pose nueva es dejar el PNG ahí y
    # nombrarlo en `cinematic.POSES`, sin tocar el build.
    datas=[('assets', 'assets')],
    # engine/* is a local package: PyInstaller follows the imports from
    # app.py, but listing the submodules explicitly means a missed import
    # fails the build instead of the finished executable.
    hiddenimports=[
        'customtkinter',
        'engine',
        'engine.theory',
        'engine.voicing',
        'engine.style',
        'engine.fitness',
        'engine.ga',
        'engine.export',
        'engine.history',
        'engine.session',
        'engine.achievements',
        # Faltaban: la lista se escribe a mano justamente para que un import
        # que no esté rompa el build y no el ejecutable ya entregado, así que
        # dejarla incompleta anula el sentido de tenerla.
        'engine.audio',
        'engine.book',
        'engine.flourish',
        'engine.harmonize',
        'engine.harmony',
        'engine.importer',
        'engine.passing',
        # El modo historia: el guion, los ruidos sintetizados y la cinemática.
        # `cinematic` no está en `engine/` pero se importa igual desde
        # `app.py`, así que va en la lista por el mismo motivo que el resto.
        'engine.story',
        'engine.ambience',
        # Los huevos de pascua: las condiciones y el contador.
        'engine.eggs',
        # Las visitas: el guion de los que se aparecen y su registro.
        'engine.visitors',
        # El experimentador de armonicos: la sintesis y el widget. Como
        # `cinematic` y `staff`, `spectrum` no vive en `engine/` y se importa
        # igual desde `app.py`.
        'engine.harmonics',
        # Los timbres de reproduccion y el lector de muestras WAV. Lo importa
        # `engine.audio`: sin el, no suena ninguna nota del programa.
        'engine.timbre',
        # El analizador: la lectura de la partitura y su pantalla. `analyzer`
        # tampoco vive en `engine/` --- como `spectrum` y `staff` --- y se
        # importa desde `app.py` igual que ellos.
        'engine.analysis',
        # El aviso de version nueva: la consulta (pura, en `engine/`) y el
        # cartel. `updater` tampoco vive en `engine/` --- como `spectrum`,
        # `staff` y `analyzer` --- y se importa desde `app.py` igual que
        # ellos. Sin estos dos, el ejecutable arranca y nunca avisa nada.
        'engine.updates',
        # Adonde va lo que se escribe en la consola cuando no hay consola.
        # Se importa antes que customtkinter: sin esto, el primer aviso de
        # una libreria mataba el ejecutable al arrancar.
        'engine.console',
        'engine.shortpath',
        # Los dos idiomas: el motor de traduccion y los catalogos. Los
        # catalogos se importan por nombre desde `engine.lang.PARTS`, o sea
        # que PyInstaller no los ve siguiendo los imports --- sin listarlos,
        # el ejecutable sale y habla castellano pase lo que pase. `chooser`
        # tampoco vive en `engine/` --- como `spectrum`, `staff`, `analyzer`
        # y `updater` --- y se importa desde `app.py` igual que ellos.
        'engine.i18n',
        'engine.lang',
        'engine.lang.en_app',
        'engine.lang.en_screens',
        'engine.lang.en_tools',
        'engine.lang.en_engine',
        'engine.lang.en_story',
        'engine.lang.en_book',
        # La escuelita: lo que se enseña y cómo se corrige (`engine.school`,
        # puro), su catálogo de traducción ---que se importa por nombre,
        # como los otros--- y la pantalla, que tampoco vive en `engine/`.
        'engine.school',
        'engine.lang.en_school',
        'school',
        'cinematic',
        'spectrum',
        'staff',
        'analyzer',
        'updater',
        'chooser',
        # Los dibujos de las tarjetas de la pantalla inicial.
        'homeart',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'scipy', 'PIL.ImageQt', 'tkinter.test'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ChordWeaver',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # Set this to True to debug a build that will not start: the console
    # window keeps the traceback visible instead of closing instantly.
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChordWeaver',
)
