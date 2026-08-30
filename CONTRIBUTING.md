# How to Contribute to ChordWeaver

Thanks for stopping by. This file is short on purpose: almost everything you need
to know to avoid breaking things is already documented in two other places, and
this file tells you which one to read before touching what.

* [`README.md`](README.md) — what the program does and how to run it.
* [`MUSIC_LOGIC.md`](MUSIC_LOGIC.md) — **mandatory reading before touching
  anything musical.** Documents, with `file:line` references, how notes, voices,
  and intervals are represented; the three different criteria for consonance and
  why they don't agree; the complete rule catalog; and the exceptions that look
  like bugs but aren't.
* [`CLAUDE.md`](CLAUDE.md) — the map of design decisions and measured
  optimizations. If something in the code seems unnecessarily weird, it's
  probably explained there, along with the numbers that justify it.

## Setting Up the Project

```bash
pip install customtkinter     # the only dependency needed to run the app
python app.py                 # the GUI application
python tests.py               # the engine test suite (369 tests)
python cli.py --chords "Cmaj7 Am7 Dm7 G7" --genre jazz
```

You must be in the directory containing `cli.py`; otherwise Python will throw
`No module named engine`.

## Before Submitting a Pull Request

1. **`python tests.py` must pass completely.** There are 369 tests and they take
   less than two minutes. Add a new test for every new behavior.
2. **If you touched `engine/fitness.py` or `engine/style.py`, also run
   `python audit.py`** and paste the result into the PR. The weights are calibrated
   against that audit: changing a single number changes the musical output of all
   generations **without causing any test to fail**. The README contains the
   control table to compare against.
3. **Say what you measured.** This project has several optimizations that are
   only justified by numbers — population filling, thread-switch intervals,
   bare Tkinter frames — and all of them are documented with before-and-after
   measurements. If your change is performance-related, measure it.

## The Five Traps That Catch Everyone

None of these produce an error. They all fail silently.

1. **If the engine is compiled, editing the `.py` file does nothing.**
   `python build_engine.py` leaves `engine/*.pyd` next to the `.py` files, and a
   `.pyd` takes precedence in the import order. You edit, run, nothing changes,
   and start looking for the bug somewhere else. `ls engine/*.pyd` tells you in
   one second whether the engine is compiled; `python build_engine.py --clean`
   switches it back to pure Python while you're working.

2. **And with the compiled engine, patching a function from `engine/` externally
   also does nothing** if the caller is in the same module: Cython resolves those
   calls at the C level. Any script that instruments the engine internally must
   be run with `--clean`. `tests.py` doesn't need this because it tests through
   the public API.

3. **A new preference that isn't included in `DEFAULT_SETTINGS`
   (`engine/history.py`) will save correctly and then disappear when reopening
   the program.** It's a whitelist: `load_settings` discards any key that isn't
   listed there.

4. **A new module in `engine/` must be added to the `hiddenimports` in
   `ChordWeaver.spec`.** They are listed manually specifically so that a missing
   import breaks the build instead of the already-shipped executable.

5. **Any script that opens the window must go through `uitest.Session`.**
   Constructing `ChordWeaverApp` directly writes to the user's real data: the
   history stores the last ten productions, so ten test runs can wipe it out
   completely. `Session` sends everything to disposable files and sets
   `CHORDWEAVER_DATA_DIR` **before importing `app`**.

## Design Boundaries

These aren't style preferences: they are what makes the project what it is. A PR
that crosses them will be discussed even if the code itself is good.

* **The engine has no dependencies.** `engine/` is pure standard-library Python.
  MusicXML, MIDI, and WAV audio are written by hand so the executable stays small
  and dependency-free: **do not introduce `music21`, `mido`, `numpy`, or any
  audio library.** The project's only actual dependency is `customtkinter`,
  which belongs to the interface.
* **No module in `engine/` imports a GUI toolkit.** This is what allows the engine
  to run from the tests, the CLI, or the application interchangeably.
* **The dependency graph has no cycles**, and `engine/session.py` is the facade:
  the GUI and CLI only communicate with that module. New engine capabilities
  should be exposed there.
* **Genre profiles only change weights and default values, never the mechanics.**
  If a new rule needs different logic depending on the genre, it should be
  implemented as a weight, not as a branch. Every switch must be independently
  toggleable: the genre defines the initial value and nothing more.
* **Paths are portable.** `history.base_directory()` returns the `.exe` folder
  when frozen and the project root when running from source. Never write to the
  user's home directory or a system location unless the user explicitly chooses
  it through a dialog. The program's artwork lives under `program_directory()`,
  which is a different thing.
* **Cython is optional, and the `.py` files aren't modified to accommodate it.**
  Types live in `engine/fitness.pxd` and `engine/style.pxd`, which Python ignores
  completely. Rewriting a function just to make it easier to declare would defeat
  the entire purpose of this separation. The `.pxd` files **are source code**:
  edit them manually, and any signature defined there must match the one in the
  corresponding `.py`.

## Code Conventions

* Python 3.9+. No automatic formatter is configured: look at the file you're
  editing and write code in the same style.
* **Identifiers and docstrings are in English; prose comments are in Spanish.**
  This is how the entire codebase is written, so please follow it.
* Long comments explain **why**, not what. The code already says what it does.
* Tk is not thread-safe: the search runs in a background thread and reports
  through a queue that the main loop drains on a timer. **The worker never touches
  a widget**, and a background thread cannot schedule anything with `after` either.

## What Not to Commit

The `.gitignore` already covers these, but just in case: `history.json`,
`achievements.json`, `story.json`, `eggs.json`, `visitors.json`, and
`settings.json` are **user data**, not code. The same goes for `output/`,
`build/`, `dist/`, and `engine/*.pyd`, which are all regenerated.

## Reporting a Bug

Explain what you expected to happen and what actually happened, and include:

* the mode (Organizer, Generator, or Harmonizer) and the genre,
* the chords or melody that triggered it,
* **the seed**, if you set one: with the same seed, the result is identical
  bit-for-bit, making it the key to reproducing the bug,
* whether the engine was compiled (`ls engine/*.pyd`).

If it's a musical bug — "this shouldn't sound like this" — explain which rule you
think is being violated and, if possible, where you found it in `MUSIC_LOGIC.md`.
Several things that look like errors are documented there as deliberate exceptions.

## License

By contributing, you agree that your contribution will be distributed under the
[MIT license](LICENSE), which is the project's license.
