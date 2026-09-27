"""Write net classes, net-class patterns and board rules into the .kicad_pro.

KiCad keeps these in the project file and rewrites it from memory when it closes,
so run this (with KiCad closed) after any regeneration, before routing:
  python setup_rules.py
Net names on the board carry the root-sheet prefix ("/GND"), so patterns do too.
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PRO = os.path.join(ROOT, "neuromorphic-ir-sensor-tht.kicad_pro")

CLASSES = {
    # name: (track, clearance, via_dia, via_drill)
    "Default": (0.3, 0.25, 0.8, 0.4),
    "Power": (0.5, 0.25, 0.8, 0.4),
    "Analog_Sensitive": (0.3, 0.3, 0.8, 0.4),
    "Digital_Events": (0.3, 0.25, 0.8, 0.4),
}
PATTERNS = [
    ("Power", "/GND"), ("Power", "/3V3"), ("Power", "/3V3A"),
    ("Analog_Sensitive", "/VREF"), ("Analog_Sensitive", "/TIA_IN_*"),
    ("Analog_Sensitive", "/VPHOTO_*"), ("Analog_Sensitive", "/VEVENT_*"),
    ("Analog_Sensitive", "/VTH_*"),
    ("Digital_Events", "/SPIKE_*"), ("Digital_Events", "/RAW_*"),
    ("Digital_Events", "/Q_ON_*"), ("Digital_Events", "/Q_OFF_*"),
    ("Digital_Events", "/LED_*"),
]


def main():
    with open(PRO, encoding="utf-8") as f:
        d = json.load(f)
    ns = d.setdefault("net_settings", {})
    template = dict(ns.get("classes", [{}])[0]) if ns.get("classes") else {}
    classes = []
    for i, (name, (tw, cl, vd, vdr)) in enumerate(CLASSES.items()):
        c = dict(template)
        c.update(name=name, track_width=tw, clearance=cl, via_diameter=vd, via_drill=vdr,
                 priority=2147483647 if name == "Default" else i)
        classes.append(c)
    ns["classes"] = classes
    ns["netclass_patterns"] = [{"netclass": c, "pattern": p} for c, p in PATTERNS]
    ns["netclass_assignments"] = None
    rules = d.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
    rules.update(min_clearance=0.2, min_track_width=0.2, min_via_diameter=0.6,
                 min_through_hole_diameter=0.3, min_copper_edge_clearance=0.5,
                 min_resolved_spokes=1)
    with open(PRO, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    print("rules written: %d classes, %d patterns" % (len(classes), len(PATTERNS)))


if __name__ == "__main__":
    main()
