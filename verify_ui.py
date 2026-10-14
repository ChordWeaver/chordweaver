import time
import uitest, traceback
import customtkinter as ctk
from engine import session
import engine.harmony as H
import engine.flourish as F
H.SET_PIECE_CHANCE = 1.0
fallos = []

def check(nombre, ok, detalle=""):
    print(f"  [{'OK ' if ok else 'MAL'}] {nombre} {detalle}")
    if not ok: fallos.append(nombre)

print("=== 1+2: cadencia cromatica ===")
s = uitest.Session()
s.mode('random').next(); s.genre('classical').next(); s.next()
s.bars(3).next(); s.key('A', H.MODES['minor'].label); s.next(); s.search(60,25)
out = s.generate()
if out and out.succeeded:
    b0 = [c[0] for c in uitest.solution_chords(out, 0)]
    check("bajo desciende", all(b0[i] > b0[i+1] for i in range(4)), f"{b0}")
    cif = [uitest.chord_symbols(out, i) for i in range(3)]
    check("cifrado solo en opcion 1", cif[1] != cif[0] or cif[2] != cif[0],
          f"op1={cif[0][:3]} op2={cif[1][:3]}")
    hdrs = s.chord_headers()
    check("barras visibles en UI", any('/' in h for h in hdrs), f"{[h for h in hdrs if '/' in h][:4]}")
s.close()

print("=== 3: ii-V en jazz ===")
con = 0
for _ in range(5):
    s = uitest.Session()
    s.mode('random').next(); s.genre('jazz').next(); s.next()
    s.bars(4).next(); s.next(); s.search(80,35)
    out = s.generate(timeout=90)
    if out and out.succeeded:
        rs = uitest.romans(out, 0)
        if any(rs[i]=='ii' and rs[i+1]=='V' for i in range(len(rs)-1)): con += 1
    s.close()
check("ii-V frecuente", con >= 4, f"{con}/5")

print("=== 5+7: gregoriano ===")
deg = plag = 0
for _ in range(5):
    s = uitest.Session()
    s.mode('random').next(); s.genre('gregorian').next(); s.next()
    s.bars(4).next(); s.next(); s.search(80,35)
    out = s.generate(timeout=90)
    if out and out.succeeded:
        rs = uitest.romans(out, 0)
        if len(set(rs)) <= 2: deg += 1
        if any(rs[i] in ('IV','iv') and rs[i+1] in ('I','i') for i in range(len(rs)-1)): plag += 1
    s.close()
check("sin degenerados", deg == 0, f"{deg}/5")
check("plagales frecuentes", plag >= 3, f"{plag}/5")

print("=== 6: marcas en las 3 opciones ===")
s = uitest.Session()
s.mode('random').next(); s.genre('jazz').next(); s.next()
s.bars(4).next(); s.next(); s.search(80,35)
out = s.generate(timeout=90)
if out and out.succeeded:
    fl = out.flourishes
    porop = {i: [m.label for m in fl.by_solution.get(i, [])] for i in range(3)}
    check("detecta en varias opciones", sum(1 for v in porop.values() if v) >= 2, f"{porop}")
    check("casillas tenidas", s.tinted() > 0, f"{s.tinted()}")
s.close()

print("=== 8: voces por defecto ===")
esperado = {'classical': 3, 'chorale': 4, 'gregorian': 3, 'jazz': 4}
for g, n in esperado.items():
    s = uitest.Session()
    s.mode('random').next(); s.genre(g).next()
    v = sorted(k for k,x in s.win.voice_check_vars.items() if x.get())
    check(f"{g} voces", len(v) == n, f"{len(v)}")
    s.close()

print("=== 9: reemplazo por 6ta ===")
F.SIXTH_CHANCE = 1.0
hecho = False
for _ in range(5):
    s = uitest.Session()
    s.mode('manual').next(); s.genre('classical').next()
    s.voices(['B','T','A','S']).next(); s.bars(3).next()
    s.chords(['A','E','A','E','A','E']).next(); s.search(60,25)
    out = s.generate(timeout=90)
    if out and out.succeeded:
        fl = getattr(out, 'flourishes', None)
        if fl and fl.sixth_slot is not None:
            ch = uitest.solution_chords(out, 0)
            i, j = fl.sixth_slot, fl.forced_slot
            check("omit5 en la UI", any('omit5' in h for h in s.chord_headers()),
                  f"{[h for h in s.chord_headers() if 'omit' in h]}")
            check("forzado sin perder notas", len(set(ch[j])) == len(set(uitest.solution_chords(out,0)[j])),
                  f"{ch[j]}")
            hecho = True
            s.close(); break
    s.close()
if not hecho: check("reemplazo ocurre", False, "no salio en 5 intentos")

print("=== 10: modo armonizar ===")
try:
    from staff import diatonic_index
    for genero in ('classical', 'chorale', 'gregorian', 'jazz'):
        s = uitest.Session()
        s.mode('harmonise').next(); s.genre(genero).next(); s.next()
        for l, o in [('C',5),('D',5),('E',5),('F',5),('G',5),('F',5),('E',5),('C',5)]:
            s.win.staff.notes.append((diatonic_index(l, o), 1.0))
        s.win.staff.redraw(); s.win._on_melody_changed()
        s.next(); s.search(70, 30)
        out = s.generate(timeout=120)
        ok = out is not None and out.succeeded
        respeta = True
        if ok:
            # Each option was built from its own progression, so its notes
            # are checked against ITS slots, not the first option's.
            voz = s.win._melody_voice
            for pos, sol in enumerate(out.result.solutions):
                slots = out.alternate_slots.get(pos, out.spec.slots)
                for i, sl in enumerate(slots):
                    fijada = sl.pinned_voices.get(voz)
                    if fijada is not None and sol.slots[i][voz] != fijada:
                        respeta = False
        check(f"armoniza en {genero}", ok and respeta)
        s.close()
except Exception as e:
    check("modo armonizar", False, f"{type(e).__name__}: {e}")

print("=== 4: cambio de genero repetido ===")
try:
    s = uitest.Session()
    for g in ('classical','jazz','gregorian','chorale','jazz','classical'):
        s.home(); s.mode('random').next(); s.genre(g).next(); s.next()
        s.bars(2).next(); s.next(); s.search(50,20)
        o = s.generate(timeout=60)
        if not (o and o.succeeded): raise RuntimeError(f"fallo en {g}")
    s.close()
    check("sin crash", True, "6 generaciones seguidas")
except Exception as e:
    check("sin crash", False, f"{type(e).__name__}: {e}")

print("=== 11: resultado en partitura y en tabla ===")
try:
    s = uitest.Session()
    s.mode('manual').next(); s.next(); s.next(); s.next()
    s.chords(["C", "Am", "Dm7", "G7", "C", "F", "G", "C"]).next()
    s.search(30, 15)
    o = s.generate(timeout=120)
    staves = s._staves()
    check("una partitura por opcion", len(staves) == len(o.result.solutions),
          f"{len(staves)} de {len(o.result.solutions)}")
    check("un cifrado por acorde",
          all(len(g.annotations) == len(o.spec.slots) for g in staves))
    check("partitura de solo lectura", all(not g.editable for g in staves))
    s.win._set_results_view("Tabla"); s.win.update()
    check("la tabla vuelve", not s._staves() and len(s.chord_headers()) >= 8,
          f"{len(s.chord_headers())} cifrados")
    s.win._set_results_view("Partitura"); s.win.update()
    check("y la partitura tambien", len(s._staves()) == len(staves))
    # «Analizar» abre la opción en el analizador, con sus notas y su estilo,
    # y volver deja el resultado como estaba.
    botones = []
    def _junta(w):
        if isinstance(w, ctk.CTkButton) and w.cget("text") == "Analizar":
            botones.append(w)
        for c in w.winfo_children():
            _junta(c)
    _junta(s.win.body)
    check("un Analizar por opcion", len(botones) == len(o.result.solutions))
    botones[1].invoke(); s.win.update()
    an = s.win.analyzer
    lanes = s.win._staff_lanes(o.spec.voices)
    lineas = session.analysis_lines(o, 1)
    check("llegan las notas de la opcion 2",
          all(an.staff.lines()[lane] == lineas[v] for v, lane in enumerate(lanes)))
    check("juzgado con el estilo del pedido", an.genre() == s.win.request.genre_key)
    s.win._close_detour(); s.win.update()
    check("volver deja el resultado", len(s._staves()) == len(staves)
          and "Buscando soluciones" not in s.labels())
    s.close()
except Exception as e:
    check("resultado en partitura", False, f"{type(e).__name__}: {e}")

print("=== 12: avisos en fila ===")
try:
    s = uitest.Session()
    from engine import achievements as AC
    for a in AC.CATALOG[:5]:
        s.win._show_toast(a)
    s.win.update()
    check("dos a la vista", len(s.win.toasts) == 2, f"{len(s.win.toasts)}")
    check("tres en fila", len(s.win._toast_backlog) == 3,
          f"{len(s.win._toast_backlog)}")
    s.win.toasts[0].close()
    end = time.time() + 1.0
    while time.time() < end:
        s.win.update(); time.sleep(0.02)
    check("el siguiente entra", len(s.win.toasts) == 2
          and len(s.win._toast_backlog) == 2)
    s.close()
except Exception as e:
    check("avisos en fila", False, f"{type(e).__name__}: {e}")

print("=== 13: un cambio de pantalla en medio de otro ===")
try:
    s = uitest.Session()
    w = s.win
    w._open_detour("history", replace=True); w.update()
    w.after_idle(lambda: w._open_detour("book", replace=True))
    started = time.time()
    w._go_home()
    end = time.time() + 1.0
    while time.time() < end:
        w.update(); time.sleep(0.02)
    check("no se cuelga", time.time() - started < 10)
    check("termina donde se pidio", bool(w.detour) and w.detour[-1][0] == "book")
    check("sin pantallas huerfanas", len(w.stage.winfo_children()) <= 2,
          f"{len(w.stage.winfo_children())}")
    s.close()
except Exception as e:
    check("redibujado reentrante", False, f"{type(e).__name__}: {e}")

print("=== 14: el tutorial sigue a la ventana ===")
try:
    import tkinter as tk

    def pump(w, seconds):
        end = time.time() + seconds
        while time.time() < end:
            w.update(); time.sleep(0.02)

    def foco(t):
        """Lo que tapan los velos, el hueco y el cartel, contra el blanco."""
        w = t.app
        w.update_idletasks()
        def caja(p):
            return (p.winfo_x(), p.winfo_y(), p.winfo_width(), p.winfo_height())
        marcos = [p for p in t.parts if type(p) is tk.Frame]
        velos = [caja(p) for p in marcos if p.cget("bg") == t.veil]
        bordes = [caja(p) for p in marcos if p.cget("bg") != t.veil]
        hueco = None
        if bordes:
            x0 = min(b[0] for b in bordes); y0 = min(b[1] for b in bordes)
            hueco = (x0, y0, max(b[0] + b[2] for b in bordes) - x0,
                     max(b[1] + b[3] for b in bordes) - y0)
        esperado = None
        blanco = t.steps[t.index].get("target")
        if blanco is not None:
            b = blanco(w)
            x = b.winfo_rootx() - w.winfo_rootx()
            y = b.winfo_rooty() - w.winfo_rooty()
            esperado = (max(0, x - 6), max(0, y - 6),
                        b.winfo_width() + 12, b.winfo_height() + 12)
        return dict(ventana=(w.winfo_width(), w.winfo_height()),
                    tapado=(max(v[0] + v[2] for v in velos),
                            max(v[1] + v[3] for v in velos)),
                    hueco=hueco, esperado=esperado, cartel=caja(t.card))

    def en_su_lugar(t, cuando):
        f = foco(t)
        W, H = f["ventana"]
        cx, cy, cw, ch = f["cartel"]
        check(f"velos a la medida {cuando}", f["tapado"] == f["ventana"],
              f"{f['tapado']} en {f['ventana']}")
        check(f"hueco sobre el blanco {cuando}", f["hueco"] == f["esperado"],
              f"{f['hueco']} vs {f['esperado']}")
        check(f"cartel adentro {cuando}",
              cx >= 0 and cy >= 0 and cx + cw <= W and cy + ch <= H,
              f"{f['cartel']}")

    s = uitest.Session()
    w = s.win
    antes = (w.bind("<Configure>"), w.bind("<Escape>"))
    w._start_tutorial(); pump(w, 0.8)
    t = w.tutorial
    t._advance(); pump(w, 0.5)              # la tarjeta del Organizador
    en_su_lugar(t, "al abrir")
    w.state("zoomed"); pump(w, 0.6)
    en_su_lugar(t, "maximizada")
    w.state("normal"); pump(w, 0.6)
    en_su_lugar(t, "restaurada")

    # Arrastrar el borde: una ráfaga de tamaños se dibuja una sola vez, y
    # mover la ventana sin cambiarle el tamaño no dibuja nada.
    dibujos = []
    dibujar = t._draw
    t._draw = lambda: (dibujos.append(1), dibujar())
    for ancho in range(1200, 1460, 20):
        w.geometry(f"{ancho}x{ancho * 2 // 3}"); w.update_idletasks()
    pump(w, 0.6)
    check("una rafaga, un dibujo", len(dibujos) == 1, f"{len(dibujos)}")
    en_su_lugar(t, "arrastrada")
    hechos = len(dibujos)
    w.geometry("+60+60"); pump(w, 0.8)
    check("moverla no redibuja", len(dibujos) == hechos,
          f"{len(dibujos) - hechos} de mas")
    t.skip(); pump(w, 0.3)
    check("desata solo lo suyo",
          (w.bind("<Configure>"), w.bind("<Escape>")) == antes)
    check("customtkinter sigue atado",
          "_update_dimensions_event" in w.bind("<Configure>"))
    s.close()

    # Las guías de pantalla son la misma clase.
    s = uitest.Session()
    w = s.win
    s.mode('manual').next(); s.next(); s.next(); s.next()   # los acordes
    antes = (w.bind("<Configure>"), w.bind("<Escape>"))
    w.guides_enabled = True
    w._start_guide("chords"); pump(w, 0.5)
    g = w.guide
    g._advance(); pump(w, 0.3)              # la primera casilla
    en_su_lugar(g, "en la guia")
    w.state("zoomed"); pump(w, 0.6)
    en_su_lugar(g, "en la guia maximizada")
    w._close_guide(); pump(w, 0.3)
    check("la guia desata lo suyo",
          (w.bind("<Configure>"), w.bind("<Escape>")) == antes)
    s.close()
except Exception as e:
    check("tutorial y ventana", False, f"{type(e).__name__}: {e}")

print("=== 15: los carteles del arranque se van del todo ===")
try:
    import os, tkinter
    import chooser, updater
    from engine import updates
    if not os.environ.get("CHORDWEAVER_TEST_ORIGIN"):
        lugar = uitest._placed("1x1")
        if lugar != "1x1":
            os.environ["CHORDWEAVER_TEST_ORIGIN"] = lugar[len("1x1"):]

    def apretar(ventana, texto):
        # Como una persona: el mouse entra y se suelta encima, que es lo que
        # escucha el botón de customtkinter. `invoke()` no pasa por la
        # animación del click, que es lo que dejaba el cartel vivo.
        pila = [ventana]
        while pila:
            w = pila.pop()
            if (w.__class__.__name__ == "CTkButton"
                    and str(w.cget("text")).startswith(texto)):
                w._canvas.event_generate("<Enter>", x=5, y=5)
                w._canvas.event_generate("<ButtonRelease-1>", x=5, y=5)
                return
            pila.extend(w.winfo_children())
        # Sin el botón la prueba no se puede quedar esperando un click.
        check(f"boton {texto}", False, "no esta")
        updater.dismiss(ventana)

    def sigue_viva(ventana):
        try:
            return bool(ventana.winfo_exists())
        except tkinter.TclError:
            return False

    vistas = []
    def elegir(ventana):
        vistas.append(ventana)
        apretar(ventana, "English")
    elegido = chooser.ask(on_ready=elegir)
    check("el idioma se elige", elegido == "en", f"{elegido}")
    check("el cartel de idioma se cierra",
          bool(vistas) and not sigue_viva(vistas[0]))

    vistas.clear()
    def ahora_no(ventana):
        vistas.append(ventana)
        apretar(ventana, "Ahora no")
    nueva = updates.Release(version="9.9", page="https://example.invalid",
                            notes="", download="", headline="")
    sigue = updater.notice(nueva, dict(updater.FALLBACK), on_ready=ahora_no)
    check("«Ahora no» abre el programa", sigue is True)
    check("el cartel de version se cierra",
          bool(vistas) and not sigue_viva(vistas[0]))
except Exception as e:
    check("carteles del arranque", False, f"{type(e).__name__}: {e}")

print("=== 16: el velo no se lleva el Escape de nadie ===")
try:
    s = uitest.Session()
    w = s.win
    ajeno = w.bind("<Escape>", lambda _e: None, add="+")
    w._open_overlay()
    check("el velo suma su Escape", ajeno in w.bind("<Escape>")
          and w._overlay_escape in w.bind("<Escape>"))
    w._close_overlay()
    check("al cerrar queda el ajeno", ajeno in w.bind("<Escape>"))
    check("y se va el del velo", "_escape_overlay" not in w.bind("<Escape>")
          and not w._overlay_escape)
    s.close()
except Exception as e:
    check("velo y Escape", False, f"{type(e).__name__}: {e}")

print("=== 17: escuelita, figuras, signos y practica ===")
try:
    import staff as pentagrama
    from engine import school as escuela

    def pump(w, seconds):
        end = time.time() + seconds
        while time.time() < end:
            w.update(); time.sleep(0.02)

    class Click:
        """Un click del mouse sobre el lienzo, sin scroll."""
        def __init__(self, x, y):
            self.x, self.y = x, y

    def escribir(ss, momento, altura, figura):
        st = ss.staff
        nombre = next(n for n, v in getattr(ss, "_figures", {}).items()
                      if v == figura) if getattr(ss, "_figures", None) else None
        if nombre:
            ss._figure_chosen(nombre)
        x = st._x_for(momento + st.duration / 2)
        indice = pentagrama.index_for_pitch(altura, st.fifths)
        y = st._y_for(indice, st.staff_of(st.active, indice))
        st._on_click(Click(x, y))
        pump(ss, 0.15)

    def abrir(ss, clave):
        item = escuela.exercise(clave)
        ss.open_lesson(escuela.lesson_of(clave), item)
        pump(ss, 0.4)
        return item

    s = uitest.Session()
    w = s.win
    w._open_detour("school"); pump(w, 1.0)
    ss = w.school_screen

    abrir(ss, "figuras_escribir")
    momento = 0.0
    for figura in (4.0, 2.0, 2.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.5):
        escribir(ss, momento, 67, figura)
        momento += figura
    ss._check(); pump(w, 0.3)
    check("figuras: escribir con el selector aprueba",
          ss.verdict is not None and ss.verdict.passed,
          f"{[r.text for r in (ss.verdict.problems if ss.verdict else [])]}")

    abrir(ss, "escribe_alteradas")
    for compas, (signo, altura) in enumerate(((1, 66), (-1, 70), (1, 73),
                                               (-1, 75))):
        ss._sign_chosen(signo)
        natural = altura - signo
        st = ss.staff
        x = st._x_for(compas * 4.0 + 2.0)
        indice = pentagrama.index_for_pitch(natural, st.fifths)
        st._on_click(Click(x, st._y_for(indice, True)))
        pump(w, 0.15)
    check("signos: se apagan despues de cada nota", ss.staff.pending is None)
    ss._check(); pump(w, 0.3)
    check("signos: sostenidos y bemoles aprueban",
          ss.verdict is not None and ss.verdict.passed,
          f"{ss.staff.lines()[3]}")

    item = abrir(ss, "completar_compases")
    escribir(ss, 0.0, 72, 1.0)          # encima de la blanca dada
    pump(w, 0.3)
    check("lo dado no se parte",
          escuela.tampered(item, ss.staff.lines()) is None)

    ss.open_lesson(escuela.lesson("clave_sol")); pump(w, 0.4)
    ss.open_practice(); pump(w, 0.5)
    for _ in range(3):
        ss._choose(escuela.correct_choice(ss.exercise)); pump(w, 0.9)
    check("practica: la racha cuenta", ss._practice["streak"] == 3
          and ss.progress.practice_best >= 3, f"{ss._practice['streak']}")
    mala = next(o.value for o in ss.exercise.options
                if o.value != escuela.correct_choice(ss.exercise))
    ss._choose(mala); pump(w, 0.2)
    check("practica: un error la corta", ss._practice["streak"] == 0)
    ss._leave_practice(); pump(w, 0.3)
    check("practica: volver deja la leccion",
          ss._practice is None and ss.exercise.key != escuela.PRACTICE_KEY)
    # Aprobar un ejercicio de una lección avanzada no pinta como hechas las
    # de atrás: cada estación llena es una lección aprobada entera.
    adelante = escuela.lessons()[20]
    ss.progress.mark_passed(adelante.exercises[0].key)
    ss.open_lesson(adelante); pump(w, 0.3)
    hechas = sum(1 for item in escuela.lessons()
                 if ss.progress.lesson_done(item))
    llenas = len(ss.trail.find_withtag("done"))
    vacias = len(ss.trail.find_withtag("pending"))
    check("recorrido: llenas sólo las aprobadas",
          llenas == hechas and llenas + vacias == len(escuela.lessons()),
          f"{llenas} llenas, {hechas} aprobadas, {vacias} pendientes")
    s.close()
except Exception as e:
    import traceback; traceback.print_exc()
    check("escuelita interactiva", False, f"{type(e).__name__}: {e}")

print("=== 18: modo profesional ===")
try:
    from engine import visitors as visitas, history as historial

    def pump(w, seconds):
        end = time.time() + seconds
        while time.time() < end:
            w.update(); time.sleep(0.02)

    s = uitest.Session()
    w = s.win
    check("viene apagado", not w.settings.get("professional"))
    w._open_config(); pump(w, 0.3)
    w._set_professional(True); pump(w, 0.5)
    check("se guarda", historial.load_settings(w.settings_path).get(
        "professional") is True)
    w._close_config(); pump(w, 0.2)
    w._story_knocking = True
    w._render(); pump(w, 0.6)
    def textos(widget):
        pila, out = [widget], []
        while pila:
            x = pila.pop()
            try:
                out.append(str(x.cget("text")))
            except Exception:
                pass
            pila.extend(x.winfo_children())
        return out
    check("el inicio no llama a la puerta",
          "Hay alguien esperando" not in textos(w))
    w._set_professional(False); pump(w, 0.2)
    w._story_knocking = True
    w._render(); pump(w, 0.6)
    check("apagado, la puerta vuelve", "Hay alguien esperando" in textos(w))
    w._set_professional(True); pump(w, 0.4)
    w._close_config(); pump(w, 0.2)
    antes = len(w._scene_queue)
    w._open_visit(visitas.BACH_BAROQUE); pump(w, 0.3)
    check("no hay visitas", w.scene is None and len(w._scene_queue) == antes)
    w._maybe_vision(); pump(w, 0.3)
    check("no hay vision", w.scene is None)
    check("el sendero no espera nada",
          w._story_awaiting("manual") is None
          and w._story_awaiting("harmonise") is None)
    w._open_graduation(); pump(w, 0.6)
    check("la graduacion sin escena", w.scene is None
          and bool(w.school.graduated) and not w._scene_queue)
    w._open_config(); pump(w, 0.3)
    w._set_professional(False); pump(w, 0.5)
    check("al apagarlo el vigia vuelve", w._story_watching)
    w._close_config()
    s.close()
except Exception as e:
    import traceback; traceback.print_exc()
    check("modo profesional", False, f"{type(e).__name__}: {e}")

print()
print("FALLOS:" if fallos else "TODO OK")
for f in fallos: print("  -", f)
