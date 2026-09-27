"""Headless schematic generator: design.py -> <project>.kicad_sch

Every connected pin gets a short wire stub and a local net label; unused pins get
no-connect flags. Symbols are embedded from the official KiCad 10 libraries.
Usage: python gen_schematic.py [--force]
"""
import math
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisexp as k  # noqa: E402
from kisexp import Sym  # noqa: E402
import design  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = "neuromorphic-ir-sensor-tht"
SCH = os.path.join(ROOT, PROJECT + ".kicad_sch")

GRID = 1.27
STUB = 2.54
CHAR_W = 1.05
PAGE_W, PAGE_H = 841.0, 594.0  # A1
MARGIN = 15.0


def U():
    return str(uuid.uuid4())


def snap(v):
    return round(v / GRID) * GRID


def eff(size=1.27, justify=None, hide=False):
    e = [Sym("effects"), [Sym("font"), [Sym("size"), size, size]]]
    if justify:
        e.append([Sym("justify")] + [Sym(j) for j in justify.split()])
    if hide:
        e.append([Sym("hide"), Sym("yes")])
    return e


def outward(angle):
    a = math.radians((angle + 180) % 360)
    return round(math.cos(a)), -round(math.sin(a)), (angle + 180) % 360


def main():
    if os.path.exists(SCH) and "--force" not in sys.argv:
        with open(SCH, encoding="utf-8") as f:
            existing = k.parse(f.read())
        if k.find(existing, "symbol"):
            print("Schematic already populated; pass --force to regenerate")
            return 1
    with open(SCH, encoding="utf-8") as f:
        root_uuid = k.find1(k.parse(f.read()), "uuid")[1]

    libsyms, pins_of = {}, {}
    for p in design.parts:
        if p["lib"] not in libsyms:
            s = k.get_symbol(p["lib"])
            libsyms[p["lib"]] = s
            pins_of[p["lib"]] = k.symbol_pins(s)

    # ---------------- build unit list with extents
    units = []
    for p in design.parts:
        allpins = pins_of[p["lib"]]
        unit_ids = sorted(p["units"].keys()) if p["units"] else [1]
        for un in unit_ids:
            netmap = p["units"].get(un, {}) if p["units"] else {}
            ups = [q for q in allpins if q["unit"] in (0, un)]
            xs = [q["x"] for q in ups] or [0]
            ys = [-q["y"] for q in ups] or [0]
            x0, x1, y0, y1 = min(xs) - 2, max(xs) + 2, min(ys) - 2, max(ys) + 2
            vertical = any(q["angle"] in (90.0, 270.0) for q in ups)
            for q in ups:
                net = netmap.get(q["number"])
                if not net:
                    continue
                dx, dy, _ = outward(q["angle"])
                L = STUB + len(net) * CHAR_W + 1
                ex, ey = q["x"] + dx * L, -q["y"] + dy * L
                x0, x1, y0, y1 = min(x0, ex), max(x1, ex), min(y0, ey), max(y1, ey)
            if vertical:
                x1 += max(len(p["ref"]), len(p["value"])) * CHAR_W + 3
            else:
                y0 -= 3
                y1 += 3
            units.append(dict(part=p, unit=un, pins=ups, netmap=netmap,
                              box=(x0, y0, x1, y1), vertical=vertical))

    # ---------------- row layout by group
    order = []
    for u in units:
        if u["part"]["group"] not in order:
            order.append(u["part"]["group"])
    placed, texts = [], []
    cx, cy, row_h = MARGIN, MARGIN + 10, 0
    for g in order:
        gunits = [u for u in units if u["part"]["group"] == g]
        if cx > MARGIN:
            cx, cy, row_h = MARGIN, cy + row_h + 9, 0
        texts.append((g, cx, cy - 4))
        for u in gunits:
            x0, y0, x1, y1 = u["box"]
            w, h = x1 - x0, y1 - y0
            if cx + w > PAGE_W - MARGIN:
                cx, cy, row_h = MARGIN, cy + row_h + 4, 0
            u["at"] = (snap(cx - x0), snap(cy - y0))
            placed.append(u)
            cx += w + 4
            row_h = max(row_h, h)
    if cy + row_h > PAGE_H - MARGIN:
        raise SystemExit("layout overflow: %.0f mm" % (cy + row_h))

    # ---------------- emit
    items = []
    flg = 0
    for u in placed:
        p, X, Y = u["part"], u["at"][0], u["at"][1]
        ref = p["ref"]
        is_pwr = p["lib"].startswith("power:")
        if is_pwr:
            flg += 1
            ref = "#FLG%02d" % flg
        x0, y0, x1, y1 = u["box"]
        if u["vertical"]:
            rpos = (X + max(q["x"] for q in u["pins"]) + 2.54, Y - 1.27, "left")
            vpos = (X + max(q["x"] for q in u["pins"]) + 2.54, Y + 1.27, "left")
        else:
            top = min(-q["y"] for q in u["pins"]) if u["pins"] else 0
            bot = max(-q["y"] for q in u["pins"]) if u["pins"] else 0
            rpos = (X, Y + top - 3.81, None)
            vpos = (X, Y + bot + 3.81, None)
        props = [
            [Sym("property"), "Reference", ref, [Sym("at"), rpos[0], rpos[1], 0], eff(justify=rpos[2])],
            [Sym("property"), "Value", p["value"], [Sym("at"), vpos[0], vpos[1], 0], eff(justify=vpos[2])],
            [Sym("property"), "Footprint", p["fp"], [Sym("at"), X, Y, 0], eff(hide=True)],
            [Sym("property"), "Datasheet", "", [Sym("at"), X, Y, 0], eff(hide=True)],
            [Sym("property"), "Description", p["desc"], [Sym("at"), X, Y, 0], eff(hide=True)],
        ]
        if p["mpn"]:
            props.append([Sym("property"), "MPN", p["mpn"], [Sym("at"), X, Y, 0], eff(hide=True)])
        sym = [Sym("symbol"), [Sym("lib_id"), p["lib"]], [Sym("at"), X, Y, 0], [Sym("unit"), u["unit"]],
               [Sym("exclude_from_sim"), Sym("no")],
               [Sym("in_bom"), Sym("no" if is_pwr or p["lib"].startswith("Mechanical:") else "yes")],
               [Sym("on_board"), Sym("no" if is_pwr else "yes")],
               [Sym("dnp"), Sym("yes" if p["dnp"] else "no")],
               [Sym("uuid"), str(uuid.uuid5(uuid.UUID(root_uuid), "%s/%d" % (ref, u["unit"])))]] + props
        for q in u["pins"]:
            sym.append([Sym("pin"), q["number"], [Sym("uuid"), U()]])
        sym.append([Sym("instances"), [Sym("project"), PROJECT,
                    [Sym("path"), "/" + root_uuid, [Sym("reference"), ref], [Sym("unit"), u["unit"]]]]])
        items.append(sym)

        for q in u["pins"]:
            px, py = snap(X + q["x"]), snap(Y - q["y"])
            if q["number"] not in u["netmap"]:
                continue
            net = u["netmap"][q["number"]]
            if net is None:
                items.append([Sym("no_connect"), [Sym("at"), px, py], [Sym("uuid"), U()]])
                continue
            dx, dy, ang = outward(q["angle"])
            lx, ly = px + dx * STUB, py + dy * STUB
            items.append([Sym("wire"), [Sym("pts"), [Sym("xy"), px, py], [Sym("xy"), lx, ly]],
                          [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
                          [Sym("uuid"), U()]])
            just = "left bottom" if ang in (0, 90) else "right bottom"
            items.append([Sym("label"), net, [Sym("at"), lx, ly, ang],
                          eff(justify=just), [Sym("uuid"), U()]])

    for t, x, y in texts:
        items.append([Sym("text"), t, [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), snap(x), snap(y), 0],
                      eff(size=2.5, justify="left bottom"), [Sym("uuid"), U()]])
    notes = design.__doc__.strip()
    items.append([Sym("text"), notes, [Sym("exclude_from_sim"), Sym("no")],
                  [Sym("at"), snap(PAGE_W - 330), snap(PAGE_H - 70), 0],
                  eff(size=1.8, justify="left bottom"), [Sym("uuid"), U()]])

    sch = [Sym("kicad_sch"), [Sym("version"), 20250610], [Sym("generator"), "eeschema"],
           [Sym("generator_version"), "10.0"], [Sym("uuid"), root_uuid], [Sym("paper"), "A1"],
           [Sym("title_block"), [Sym("title"), "Neuromorphic IR Event Sensor - Rev A-THT"],
            [Sym("rev"), "A-THT"], [Sym("comment"), 1, "All through-hole, hand-assemblable variant"]],
           [Sym("lib_symbols")] + list(libsyms.values())] + items + \
          [[Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]], [Sym("embedded_fonts"), Sym("no")]]
    with open(SCH, "w", encoding="utf-8", newline="\n") as f:
        f.write(k.dump(sch) + "\n")
    print("wrote %s: %d parts, %d units, %d labels" % (
        SCH, len(design.parts), len(placed), sum(1 for i in items if i[0] == "label")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
