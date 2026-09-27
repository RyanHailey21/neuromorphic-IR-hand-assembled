"""Headless PCB generator: schematic netlist -> placed (unrouted) .kicad_pcb

Run with KiCad's bundled Python (needs pcbnew):
  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" gen_pcb.py [--force]
Footprints are loaded from the official KiCad 10 libraries only.
Board: 100 x 100 mm, 2 layers, optical end at the top edge.
"""
import os
import subprocess
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisexp as k  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROJECT = "neuromorphic-ir-sensor-tht"
PCB = os.path.join(ROOT, PROJECT + ".kicad_pcb")
SCH = os.path.join(ROOT, PROJECT + ".kicad_sch")
NET = os.path.join(ROOT, "reports", "netlist.net")
CLI = os.path.join(k.KICAD, "bin", "kicad-cli.exe")

X0, Y0, W, H = 100.0, 100.0, 100.0, 100.0
GAP = 0.8

mm = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + y))


# ------------------------------------------------------------------ placement plan
# explicit: ref -> (cx, cy, rot)  (board-relative mm, courtyard-centre)
FIXED = {
    "H1": (4, 4, 0), "H2": (96, 4, 0), "H3": (4, 96, 0), "H4": (96, 96, 0),
    # 2x2 photodiode cluster (lens axis at 50, 18.6); cathodes face their op-amp
    "D1": (46.1, 15.2, 0), "D3": (46.1, 22.0, 0),        # TL, BL -> U2 (left)
    "D2": (53.9, 15.2, 180), "D4": (53.9, 22.0, 180),    # TR, BR -> U3 (right)
    "U2": (35.0, 18.6, 180), "U3": (65.0, 18.6, 0),
    "LED1": (50.0, 34.5, 0),
    "J2": (22.0, 4.2, 90),
    "J4": (20.5, 94.8, 90), "TP2": (34.8, 94.8, 0),
    "J1": (48.0, 92.6, 90), "TP1": (61.3, 94.8, 0),
    "J5": (76.5, 94.8, 90),
}

# regions: (x0, y0, x1, y1, [refs])  shelf-packed in order
COLS = [(2, 25), (26, 50), (51, 75), (76, 98)]
REGIONS = [
    (2, 9, 17, 37, ["FB1", "C1", "C2", "U1", "R1", "C3", "C4"]),
    (18.5, 8, 29.6, 31, ["R6", "C9", "R12", "C13", "C7"]),           # U2 feedback (TL, BL)
    (70.4, 8, 81.5, 31, ["R9", "C11", "R15", "C15", "C8"]),           # U3 feedback (TR, BR)
    (83, 9, 98, 37, ["R2", "R3", "R4", "R5", "C5", "C6", "J3"]),      # thresholds + LED_EN jumper
    (29, 30.3, 44, 40.2, ["R39", "R40"]),
    (56, 30.3, 71, 40.2, ["Q1", "C33", "R38"]),
]
for (x0, x1), cmp_u, os_u, ch in zip(COLS, ["U4", "U5", "U6", "U7"], ["U8", "U9", "U10", "U11"],
                                     [("C10", "R7", "R8", "R18", "C17"), ("C12", "R10", "R11", "R19", "C18"),
                                      ("C14", "R13", "R14", "R20", "C19"), ("C16", "R16", "R17", "R21", "C20")]):
    REGIONS.append((x0, 41, x1, 58.6, [cmp_u] + list(ch)))
os_parts = {"U8": ["C21", "C22", "R22", "C23", "R24", "R23", "R25"],
            "U9": ["C24", "C25", "R26", "C26", "R28", "R27", "R29"],
            "U10": ["C27", "C28", "R30", "C29", "R32", "R31", "R33"],
            "U11": ["C30", "C31", "R34", "C32", "R36", "R35", "R37"]}
for (x0, x1), u in zip(COLS, ["U8", "U9", "U10", "U11"]):
    REGIONS.append((x0, 59.5, x1, 88.5, [u] + os_parts[u]))

ROT = {"J3": 90}  # default rotation 0 for everything packed


# ------------------------------------------------------------------ helpers
def load_netlist():
    subprocess.run([CLI, "sch", "export", "netlist", "-o", NET, SCH], check=True,
                   stdout=subprocess.DEVNULL)
    n = k.parse(open(NET, encoding="utf-8").read())
    comps = {}
    for c in k.find(k.find1(n, "components"), "comp"):
        ref = k.find1(c, "ref")[1]
        comps[ref] = dict(value=k.find1(c, "value")[1], fp=k.find1(c, "footprint")[1],
                          tstamp=k.find1(c, "tstamps")[1] if k.find1(c, "tstamps") else "",
                          pins={})
    for net in k.find(k.find1(n, "nets"), "net"):
        name = k.find1(net, "name")[1]
        for nd in k.find(net, "node"):
            r = k.find1(nd, "ref")[1]
            if r in comps:
                comps[r]["pins"][k.find1(nd, "pin")[1]] = name
    return comps


def crt_bbox(fp):
    fp.BuildCourtyardCaches()
    for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        poly = fp.GetCourtyard(layer)
        if poly.OutlineCount():
            return poly.BBox()
    return fp.GetBoundingBox(False)


def place(fp, cx, cy, rot):
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(P(cx, cy))
    bb = crt_bbox(fp)
    c = bb.GetCenter()
    fp.Move(pcbnew.VECTOR2I(P(cx, cy).x - c.x, P(cx, cy).y - c.y))


def size(fp):
    bb = crt_bbox(fp)
    return pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())


def main():
    if os.path.exists(PCB) and "--force" not in sys.argv:
        if len(pcbnew.LoadBoard(PCB).GetFootprints()):
            print("PCB already populated; pass --force to regenerate")
            return 1
    comps = load_netlist()
    if os.path.exists(PCB):
        os.remove(PCB)
    board = pcbnew.NewBoard(PCB)

    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = mm(0.2)
    ds.m_MinClearance = mm(0.2)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.5)

    nets = {}

    def net(name):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni
        return nets[name]

    fps = {}
    for ref, c in sorted(comps.items()):
        lib, name = c["fp"].split(":")
        fp = pcbnew.FootprintLoad(os.path.join(k.FPDIR, lib + ".pretty"), name)
        if fp is None:
            raise SystemExit("footprint not found: " + c["fp"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetFPIDAsString(c["fp"])
        if c["tstamp"]:
            fp.SetPath(pcbnew.KIID_PATH("/" + c["tstamp"]))
        for pad in fp.Pads():
            n = c["pins"].get(pad.GetNumber())
            if n and not n.startswith("unconnected-"):
                pad.SetNet(net(n))
        board.Add(fp)
        fps[ref] = fp

    for ref, (cx, cy, rot) in FIXED.items():
        place(fps[ref], cx, cy, rot)

    overflow = []
    done = set(FIXED)
    rects = []
    for ref in FIXED:
        bb = crt_bbox(fps[ref])
        rects.append((pcbnew.ToMM(bb.GetLeft()) - X0, pcbnew.ToMM(bb.GetTop()) - Y0,
                      pcbnew.ToMM(bb.GetRight()) - X0, pcbnew.ToMM(bb.GetBottom()) - Y0))

    def free(a):
        return all(a[2] + GAP <= b[0] or b[2] + GAP <= a[0] or a[3] + GAP <= b[1] or b[3] + GAP <= a[1]
                   for b in rects)

    for x0, y0, x1, y1, refs in REGIONS:
        for ref in refs:
            fp = fps[ref]
            fp.SetOrientationDegrees(ROT.get(ref, 0))
            w, h = size(fp)
            spot = None
            y = y0
            while spot is None and y + h <= y1 + 1e-6:
                x = x0
                while x + w <= x1 + 1e-6:
                    if free((x, y, x + w, y + h)):
                        spot = (x, y)
                        break
                    x += 0.25
                y += 0.25
            if spot is None:
                overflow.append(ref)
                continue
            place(fp, spot[0] + w / 2, spot[1] + h / 2, ROT.get(ref, 0))
            rects.append((spot[0], spot[1], spot[0] + w, spot[1] + h))
            done.add(ref)
    missing = sorted(set(fps) - done)

    # outline
    rect = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_RECT)
    rect.SetStart(P(0, 0))
    rect.SetEnd(P(W, H))
    rect.SetLayer(pcbnew.Edge_Cuts)
    rect.SetWidth(mm(0.1))
    board.Add(rect)

    # silkscreen titles
    for txt, x, y, s in (("NEUROMORPHIC IR EVENT SENSOR  Rev A-THT", 50, 41.2 - 2.2, 1.0),):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(txt)
        t.SetPosition(P(x, y))
        t.SetLayer(pcbnew.B_SilkS)
        t.SetMirrored(True)
        t.SetTextSize(pcbnew.VECTOR2I(mm(s), mm(s)))
        t.SetTextThickness(mm(0.15))
        board.Add(t)

    board.Save(PCB)
    print("placed %d footprints, %d nets; overflow=%s missing=%s" % (
        len(fps), len(nets), overflow, missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
