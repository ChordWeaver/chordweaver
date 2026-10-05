import time
import uitest, traceback
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

print()
print("FALLOS:" if fallos else "TODO OK")
for f in fallos: print("  -", f)
