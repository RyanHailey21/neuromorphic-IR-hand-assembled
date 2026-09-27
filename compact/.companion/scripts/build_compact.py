"""Build the compact board end-to-end with kicad-companion (headless).

  uv --directory C:/Users/ryanh/kicad-companion run python build_compact.py [W H]

Geometry assumptions (edit below if your holder differs):
  * M12 lens holder with 2x M2 screws at 20 mm pitch, base keep-out 23 x 16 mm, centred on
    the photodiode quad. Only the photodiodes sit inside it; everything else goes around it
    or on the back.
  * Top side: photodiodes, holder, TSAL6200. Bottom side: electronics, connector, test pads.
"""
import json
import os
import sys

from kicad_companion.schematic_builder import generate_schematic
from kicad_companion.symbols import create_derived_symbol
from kicad_companion.pcb_builder import build_pcb_from_schematic
from kicad_companion.netclasses import configure_netclasses
from kicad_companion.router import autoroute_board
from kicad_companion.finalize import finalize_pcb
from kicad_companion.placement import sanitize_silkscreen, check_placement_overlaps
from kicad_companion.drc_triage import triage_pcb_drc
from kicad_companion.pinout_audit import audit_component_pinouts

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NAME = "neuromorphic-ir-sensor-compact"
SCH = os.path.join(ROOT, NAME + ".kicad_sch")
PCB = os.path.join(ROOT, NAME + ".kicad_pcb")
SPEC = os.path.join(ROOT, "design", "spec.json")

HOLE_PITCH = 20.0          # M12 holder screw pitch
HOLDER = (23.0, 17.0)      # holder base keep-out (w, h)
LENS_Y = 9.0               # lens axis distance from top edge
PD_DX, PD_DY = 2.5, 4.05   # photodiode quad offsets (parts rotated 90 deg so the quad clears the screws)
PASSES = 20                # Freerouting passes per size attempt


def plan(W, H):
    cx, cy = W / 2, LENS_Y
    hw, hh = HOLDER[0] / 2, HOLDER[1] / 2
    fixed = {
        "D1": [cx - PD_DX, cy - PD_DY, 90, "F"], "D2": [cx + PD_DX, cy - PD_DY, 90, "F"],
        "D3": [cx - PD_DX, cy + PD_DY, 270, "F"], "D4": [cx + PD_DX, cy + PD_DY, 270, "F"],
        "H1": [cx - HOLE_PITCH / 2, cy, 0, "F"], "H2": [cx + HOLE_PITCH / 2, cy, 0, "F"],
        "LED1": [cx, cy + hh + 0.3 + 3.3, 0, "F"],
        # dual TIAs directly behind their photodiode pairs
        "U2": [cx - PD_DX - 0.6, cy, 0, "B"], "U3": [cx + PD_DX + 0.6, cy, 0, "B"],
    }
    regions = []   # connectivity placement clusters everything around the fixed parts
    keepouts = [{"rect": [cx - hw, cy - hh, cx + hw, cy + hh], "side": "F"}]
    graphics = [{"layer": "F.Fab", "rect": [cx - hw, cy - hh, cx + hw, cy + hh], "width": 0.1},
                {"layer": "F.Fab", "text": "M12 HOLDER", "at": [cx, cy - hh + 1.0], "size": 0.8}]
    return fixed, regions, keepouts, graphics


def main():
    place_only = "--place-only" in sys.argv
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    sizes = [(float(argv[0]), float(argv[1]))] if len(argv) > 1 else \
        [(28, 27), (29, 28), (30, 29), (30, 30), (32, 31)]

    print(create_derived_symbol(ROOT, "Amplifier_Operational:MCP6022", "OPA2381_DRB",
                                [{"number": "9", "name": "EP", "type": "passive", "like": "4", "dx": 2.54}],
                                properties={"Footprint": "Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.65x2.4mm"}, overwrite=True))
    sch = generate_schematic(SPEC, SCH, overwrite=True)
    print("schematic:", sch["status"], sch["paper"], "ERC", sch.get("erc", {}).get("violations"), sch["warnings"][:5])
    if sch["status"] not in ("success",):
        print(json.dumps(sch.get("erc"), indent=1)); return 1

    def set_rules(clearance):
        # Route with a little extra clearance (Freerouting lands ~10 um tighter than asked),
        # then verify against the real 5-mil rule.
        configure_netclasses(ROOT, classes={
            "Default": {"track_width": 0.14, "clearance": clearance, "via_diameter": 0.5, "via_drill": 0.3},
            "Power": {"track_width": 0.25, "clearance": clearance, "via_diameter": 0.5, "via_drill": 0.3},
            "Analog_Sensitive": {"track_width": 0.15, "clearance": clearance, "via_diameter": 0.5, "via_drill": 0.3},
        }, assignments={"Analog_Sensitive": ["VREF", "TIA_IN_*", "VPHOTO_*", "VEVENT_*", "VTH_*"]},
            overwrite_classes=True, replace_patterns=True,
            board_rules={"min_clearance": 0.127, "min_track_width": 0.1, "min_via_diameter": 0.45,
                         "min_through_hole_diameter": 0.25, "min_hole_clearance": 0.2, "min_resolved_spokes": 1,
                         "min_copper_edge_clearance": 0.3})
    ROUTE_CLEARANCE, DRC_CLEARANCE = 0.127, 0.127

    for W, H in sizes:
        fixed, regions, keepouts, graphics = plan(W, H)
        b =build_pcb_from_schematic(SCH, PCB, board_width_mm=W, board_height_mm=H, fixed=fixed, regions=regions,
                                     keepouts=keepouts, graphics=graphics, auto_sides=["B", "F"],
                                     copper_layers=4, planes={"In1.Cu": "GND"}, gap_mm=0.25, margin_mm=0.4, overwrite=True)
        pl = b["placement"]
        print(f"{W}x{H}: placed {pl['placed']} overflow {pl['overflow']} score {pl['placement_score']} drc_crt {pl['drc_courtyard_violations']}")
        if pl["overflow"] or b["missing_footprints"]:
            continue
        if place_only:
            print("placement only; stopping")
            return 0
        set_rules(ROUTE_CLEARANCE)
        r = autoroute_board(PCB, passes=PASSES, rounds=3)
        print("  rounds:", r["rounds"])
        set_rules(DRC_CLEARANCE)
        # top/bottom GND pours connect ground pads the router left to the plane
        finalize_pcb(PCB, pour_net="GND", pour_layers=["F.Cu", "B.Cu"], clearance_mm=0.2,
                     thermal_gap_mm=0.2, spoke_width_mm=0.25, min_width_mm=0.2)
        d = triage_pcb_drc(PCB, refill_zones=True)
        unrouted = d["total_unconnected"]
        print(f"  routed: {r['routing']['total_segments']} segs {r['routing']['total_vias']} vias, unconnected {unrouted}, critical {len(d['critical_errors'])}")
        if unrouted == 0 and not d["critical_errors"]:
            break
    else:
        print("no size fitted"); return 1

    print("finalize:", finalize_pcb(PCB, pour_net="GND", pour_layers=["F.Cu", "B.Cu"], clearance_mm=0.2,
                                    thermal_gap_mm=0.2, spoke_width_mm=0.25, min_width_mm=0.2).get("pours"))
    s = sanitize_silkscreen(PCB, hide_passives=True, text_size_mm=0.8)
    print("silk:", s["status"], "hidden", len(s["hidden_references"]), "remaining", s["remaining_silk_offenders"])
    d = triage_pcb_drc(PCB, refill_zones=True, schematic_parity=True)
    print(d["summary_markdown"])
    for e in d["critical_errors"][:8] + d["fab_hazards"][:5] + d["cosmetics"][:5]:
        print("  ", e["type"], e["description"], [i["description"] for i in e["items"]])
    print("parity:", d["total_parity_issues"], d["schematic_parity"][:5])
    a = audit_component_pinouts(PCB)
    print("audit:", a["verdict"], a["polarity_and_pinout_warnings"], a["floating_pads"])
    c = check_placement_overlaps(PCB, min_clearance_mm=0.2)
    print("placement:", c["placement_score"], c["is_pass"], c["drc_courtyard_violations"], c["edge_violations"][:3])
    print(f"FINAL SIZE {W} x {H} mm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
