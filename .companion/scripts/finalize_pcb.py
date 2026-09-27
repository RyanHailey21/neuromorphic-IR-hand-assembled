"""Post-route finishing: GND pours (both layers), readable silkscreen, board titles.

Run with KiCad's bundled Python after autorouting:
  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" finalize_pcb.py
"""
import os
import subprocess
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisexp as k  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PCB = os.path.join(ROOT, "neuromorphic-ir-sensor-tht.kicad_pcb")
X0, Y0, W, H = 100.0, 100.0, 100.0, 100.0
mm = pcbnew.FromMM


def P(x, y):
    return pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + y))


# refs that don't fit cleanly on silk; still on F.Fab and in the assembly drawing
HIDE = {"U1", "J3"}


def main():
    b = pcbnew.LoadBoard(PCB)

    # ---------------- re-link footprints to (regenerated) schematic symbols
    net = os.path.join(ROOT, "reports", "netlist.net")
    subprocess.run([os.path.join(k.KICAD, "bin", "kicad-cli.exe"), "sch", "export", "netlist", "-o", net,
                    PCB.replace(".kicad_pcb", ".kicad_sch")], check=True, stdout=subprocess.DEVNULL)
    comps = {}
    for c in k.find(k.find1(k.parse(open(net, encoding="utf-8").read()), "components"), "comp"):
        comps[k.find1(c, "ref")[1]] = c
    # schematic "unconnected-(...)" nets on intentionally unused pins
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}
    for n in k.find(k.find1(k.parse(open(net, encoding="utf-8").read()), "nets"), "net"):
        name = k.find1(n, "name")[1]
        if not name.startswith("unconnected-"):
            continue
        for nd in k.find(n, "node"):
            fp = fps.get(k.find1(nd, "ref")[1])
            pad = fp.FindPadByNumber(k.find1(nd, "pin")[1]) if fp else None
            if pad is not None and pad.GetNetCode() <= 0:
                ni = b.FindNet(name)
                if ni is None:
                    ni = pcbnew.NETINFO_ITEM(b, name)
                    b.Add(ni)
                pad.SetNet(ni)
    for fp in b.GetFootprints():
        c = comps.get(fp.GetReference())
        if c is not None:
            fp.SetPath(pcbnew.KIID_PATH("/" + k.find1(c, "tstamps")[1]))
            fp.SetValue(k.find1(c, "value")[1])
            props = {k.find1(pr, "name")[1] for pr in k.find(c, "property")}
            fp.SetDNP("dnp" in props)
            fp.SetExcludedFromBOM("exclude_from_bom" in props)
            desc = k.find1(c, "description")
            fp.SetField("Description", desc[1] if desc and len(desc) > 1 else "")
            for fld in k.find(k.find1(c, "fields") or [], "field"):
                name = k.find1(fld, "name")[1]
                if name == "MPN":
                    fp.SetField("MPN", fld[2] if len(fld) > 2 else "")
                    fp.GetField("MPN").SetVisible(False)
    # GND pads are also tied in by routed tracks, so one resolved spoke is enough
    b.GetDesignSettings().m_MinResolvedSpokes = 1

    # ---------------- GND pours
    gnd = b.FindNet("GND") or b.FindNet("/GND")
    zones = list(b.Zones())
    if not zones:
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            z = pcbnew.ZONE(b)
            z.SetLayer(layer)
            z.SetNet(gnd)
            ol = z.Outline()
            ol.NewOutline()
            for x, y in ((0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)):
                ol.Append(mm(X0 + x), mm(Y0 + y))
            b.Add(z)
            zones.append(z)
    for z in zones:
        z.SetLocalClearance(mm(0.4))
        z.SetMinThickness(mm(0.3))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(mm(0.3))
        z.SetThermalReliefSpokeWidth(mm(0.4))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())

    # ---------------- silkscreen: refs centred on part bodies, small but legible
    for fp in b.GetFootprints():
        ref = fp.Reference()
        name = str(fp.GetFPID().GetLibItemName())
        fp.Value().SetVisible(False) if fp.Value().GetLayer() == pcbnew.F_SilkS else None
        if ref.GetText().startswith("H") or ref.GetText() in HIDE or name.startswith("CP_Radial"):
            ref.SetVisible(False)
            continue
        fp.BuildCourtyardCaches()
        bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
        c = bb.GetCenter()
        ref.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        ref.SetTextThickness(mm(0.15))
        ref.SetTextAngleDegrees(0)
        ref.SetKeepUpright(True)
        if name.startswith(("PinHeader", "IDC", "TestPoint")):
            ref.SetPosition(pcbnew.VECTOR2I(c.x, bb.GetTop() - mm(0.8)))
        elif name.startswith("CP_Radial"):
            # inside the can outline, above the pads
            ref.SetTextSize(pcbnew.VECTOR2I(mm(0.7), mm(0.7)))
            ref.SetPosition(pcbnew.VECTOR2I(c.x, c.y - mm(1.7)))
        elif name.startswith("TO-92") and ref.GetText() == "U1":
            ref.SetPosition(pcbnew.VECTOR2I(c.x, bb.GetBottom() + mm(0.6)))
        elif name.startswith("TO-92") or name.startswith("LED_D5"):
            ref.SetPosition(pcbnew.VECTOR2I(c.x, bb.GetTop() - mm(0.7)))
        else:
            ref.SetPosition(c)

    # ---------------- titles
    for d in [d for d in b.Drawings() if d.GetClass() == "PCB_TEXT"]:
        b.Remove(d)
    for txt, x, y in (("NEUROMORPHIC IR EVENT SENSOR", 14.5, 38.3), ("Rev A-THT  hand-assembly", 14.5, 39.7)):
        t = pcbnew.PCB_TEXT(b)
        t.SetText(txt)
        t.SetPosition(P(x, y))
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9)))
        t.SetTextThickness(mm(0.15))
        b.Add(t)
    b.Save(PCB)
    print("finalized: zones filled, silkscreen arranged")


if __name__ == "__main__":
    main()
