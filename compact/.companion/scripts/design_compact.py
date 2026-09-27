"""Neuromorphic IR Event Sensor - Rev A-C (compact, PCBWay-assembled).

Smallest-footprint build of the Rev A spec. Writes compact/design/spec.json for
kicad-companion's generate_schematic.

Changes vs the SMD spec (docs/DESIGN_SPECIFICATION.md):
  OPA381 x4 (MSOP)          -> OPA2381AIDRBR x2 (same amplifier, dual, DFN-8 3x3, EP -> V-)
  TLV3202AIDR (SOIC)        -> TLV3202AIDGKR (VSSOP-8)
  74LVC1G123 (8x)           -> SN74LVC1G123DCUR (VSSOP-8 2.3x2)
  REF3312AIDBZR (SOT-23)    -> REF3312AIDCKR (SC70-3)
  VBPW34FASR                -> ams OSRAM BPW 34 FAS (same DIL-SMT package, daylight filter)
  One-shot 8.2k / 12nF      -> 100k / 1nF C0G (0201 C0G tops out ~1nF; K=1 -> ~100 us)
  Passives 0603/1206        -> 0201 (0402 for 0.1% thresholds, 10uF bulk, LED resistor)
  Debug header + 100R       -> bottom-side test pads (VPHOTO_x directly)
  LED_EN (no pin in spec)   -> 3-pad solder jumper, default bridged to 3V3 (LED on)
  2x5 2.54 keyed header     -> 2x5 1.27 mm SMD header (same pinout)
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "design", "spec.json")
LIB = "neuromorphic-ir-sensor-compact"

R0201 = "Resistor_SMD:R_0201_0603Metric"
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0201 = "Capacitor_SMD:C_0201_0603Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
CH = ["TL", "TR", "BL", "BR"]

parts = []
count = {}


def ref(prefix):
    count[prefix] = count.get(prefix, 0) + 1
    return f"{prefix}{count[prefix]}"


def add(prefix, lib_id, value, fp, pins, group, desc="", mpn="", mfr="", dnp=False, r=None):
    fields = {}
    if mpn:
        fields["MPN"] = mpn
    if mfr:
        fields["Manufacturer"] = mfr
    parts.append({"ref": r or ref(prefix), "lib_id": lib_id, "value": value, "footprint": fp,
                  "pins": pins, "fields": fields, "description": desc, "dnp": dnp, "group": group})


def R(value, a, b, group, desc, fp=R0201, mpn=None, dnp=False):
    add("R", "Device:R", value, fp, {"1": a, "2": b}, group, desc,
        mpn or f"{value} {'0402' if fp == R0402 else '0201'} thick film 1%", "Any", dnp)


def C(value, a, b, group, desc, fp=C0201, mpn="", mfr="Murata"):
    add("C", "Device:C", value, fp, {"1": a, "2": b}, group, desc, mpn, mfr)


CAP_100N = "GRM033R71A104KA01D"   # 0201 100nF 10V X7R
CAP_47P = "GRM0335C1H470JA01D"    # 0201 47pF 50V C0G
CAP_1N = "GRM0335C1H102JA01D"     # 0201 1nF 50V C0G
CAP_1U = "GRM033R60J105MEA2D"     # 0201 1uF 6.3V X5R
CAP_10U = "GRM155R60J106ME15D"    # 0402 10uF 6.3V X5R

# ---------------------------------------------------------------- power & reference
G = "Power & Reference"
add("FB", "Device:FerriteBead", "600R@100MHz", "Inductor_SMD:L_0402_1005Metric", {"1": "3V3", "2": "3V3A"}, G,
    "Analog rail filter bead", "BLM15AG601SN1D", "Murata")
C("10uF", "3V3A", "GND", G, "Analog bulk", C0402, CAP_10U)
C("10uF", "3V3", "GND", G, "Logic bulk", C0402, CAP_10U)
add("U", "Reference_Voltage:REF3012", "REF3312AIDCKR", "Package_TO_SOT_SMD:SOT-323_SC-70",
    {"1": "3V3A", "2": "VREF", "3": "GND"}, G, "1.25 V reference", "REF3312AIDCKR", "Texas Instruments", r="U1")
count["U"] = 1
C("100nF", "3V3A", "GND", G, "U1 input decoupling", mpn=CAP_100N)
C("1uF", "VREF", "GND", G, "Reference decoupling", mpn=CAP_1U)
C("100nF", "VREF", "GND", G, "Reference decoupling", mpn=CAP_100N)
R("499k 0.1%", "3V3A", "VTH_ON", G, "ON threshold upper", R0402, "499k 0.1% 0402 thin film")
R("10k 0.1%", "VTH_ON", "VREF", G, "ON threshold lower", R0402, "10k 0.1% 0402 thin film")
R("10k 0.1%", "VREF", "VTH_OFF", G, "OFF threshold upper", R0402, "10k 0.1% 0402 thin film")
R("301k 0.1%", "VTH_OFF", "GND", G, "OFF threshold lower", R0402, "301k 0.1% 0402 thin film")
C("100nF", "VTH_ON", "GND", G, "Threshold filter", mpn=CAP_100N)
C("100nF", "VTH_OFF", "GND", G, "Threshold filter", mpn=CAP_100N)

# ---------------------------------------------------------------- photodiodes + TIAs
for x in CH:
    add("D", "Sensor_Optical:BPW34", "BPW 34 FAS", "OptoDevice:Osram_BPW34S-SMD",
        {"1": "TIA_IN_" + x, "2": "GND"}, "Photodiodes", f"IR photodiode {x} (cathode = pad 1, large pad)",
        "BPW 34 FAS", "ams OSRAM")
for a, b in (("TL", "BL"), ("TR", "BR")):
    u = ref("U")
    add("U", f"{LIB}:OPA2381_DRB", "OPA2381AIDRBR", "Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.65x2.4mm",
        {"3": "VREF", "2": "TIA_IN_" + a, "1": "VPHOTO_" + a,
         "5": "VREF", "6": "TIA_IN_" + b, "7": "VPHOTO_" + b,
         "8": "3V3A", "4": "GND", "9": "GND"}, "TIA", f"Dual TIA {a}/{b}", "OPA2381AIDRBR", "Texas Instruments", r=u)
    C("100nF", "3V3A", "GND", "TIA", f"{u} decoupling", mpn=CAP_100N)
for x in CH:
    g = "Channel " + x
    R("18k 0.1%", "TIA_IN_" + x, "VPHOTO_" + x, g, "TIA feedback RF", mpn="18k 0.1% 0201 thin film")
    C("47pF", "TIA_IN_" + x, "VPHOTO_" + x, g, "TIA feedback CF", mpn=CAP_47P)
    C("100nF", "VPHOTO_" + x, "VEVENT_" + x, g, "Adaptation CA", mpn=CAP_100N)
    R("22k", "VEVENT_" + x, "VREF", g, "Adaptation RA")

# ---------------------------------------------------------------- comparators
for x in CH:
    g = "Channel " + x
    u = ref("U")
    add("U", "Comparator:MCP6562", "TLV3202AIDGKR", "Package_SO:VSSOP-8_3x3mm_P0.65mm",
        {"3": "VEVENT_" + x, "2": "VTH_ON", "1": "RAW_ON_" + x,
         "5": "VTH_OFF", "6": "VEVENT_" + x, "7": "RAW_OFF_" + x, "8": "3V3A", "4": "GND"},
        g, "Dual comparator ON (A) / OFF (B)", "TLV3202AIDGKR", "Texas Instruments", r=u)
    C("100nF", "3V3A", "GND", g, f"{u} decoupling", mpn=CAP_100N)
    R("1M", "RAW_ON_" + x, "VEVENT_" + x, g, "Optional ON hysteresis (DNP)", dnp=True)

# ---------------------------------------------------------------- one-shots
for x in CH:
    for pol in ("ON", "OFF"):
        g = "One-shot " + x
        u = ref("U")
        add("U", "74xGxx:74LVC1G123", "SN74LVC1G123DCUR", "Package_SO:VSSOP-8_2.3x2mm_P0.5mm",
            {"1": "GND", "2": f"RAW_{pol}_{x}", "3": "3V3", "4": "GND", "5": f"Q_{pol}_{x}",
             "6": f"CX_{pol}_{x}", "7": f"RC_{pol}_{x}", "8": "3V3"},
            g, f"One-shot {pol} {x}", "SN74LVC1G123DCUR", "Texas Instruments", r=u)
        C("100nF", "3V3", "GND", g, f"{u} decoupling", mpn=CAP_100N)
        C("1nF", f"CX_{pol}_{x}", f"RC_{pol}_{x}", g, "Timing C (C0G)", mpn=CAP_1N)
        R("100k", f"RC_{pol}_{x}", "3V3", g, "Timing R (~100 us)")
        R("150", f"Q_{pol}_{x}", f"SPIKE_{pol}_{x}", g, "Spike series R")

# ---------------------------------------------------------------- IR illumination
G = "IR illumination"
add("LED", "Device:LED", "TSAL6200", "LED_THT:LED_D5.0mm_IRGrey", {"1": "LED_K", "2": "LED_A"}, G,
    "940 nm IR emitter (spec part; small SMD IR LEDs are far dimmer at 250 mm)", "TSAL6200", "Vishay")
R("82", "3V3", "LED_A", G, "LED current ~22 mA", R0402, "82R 0402 1% (62.5 mW)")
add("Q", "Transistor_FET:AO3400A", "AO3400A", "Package_TO_SOT_SMD:SOT-23", {"1": "Q_G", "2": "GND", "3": "LED_K"},
    G, "LED low-side switch", "AO3400A", "Alpha & Omega")
R("100", "LED_EN", "Q_G", G, "Gate resistor")
R("100k", "Q_G", "GND", G, "Gate pulldown")
C("10uF", "3V3", "GND", G, "LED local bulk", C0402, CAP_10U)
add("JP", "Jumper:SolderJumper_3_Bridged12", "LED_EN", "Jumper:SolderJumper-3_P1.3mm_Bridged12_Pad1.0x1.5mm",
    {"1": "3V3", "2": "LED_EN", "3": "GND"}, G, "Bridged 1-2 = LED on; cut and bridge 2-3 = off")

# ---------------------------------------------------------------- connector, test pads, holes
G = "Connectors"
j1 = {"1": "GND", "2": "3V3"}
for i, x in enumerate(CH):
    j1[str(3 + 2 * i)] = "SPIKE_ON_" + x
    j1[str(4 + 2 * i)] = "SPIKE_OFF_" + x
add("J", "Connector_Generic:Conn_02x05_Odd_Even", "FPGA", "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD",
    j1, G, "2x5 1.27 mm event header (spec pinout)", "2x5 1.27mm SMD pin header, gold", "Any")
# 3V3 and GND are also on J1 pins 2 and 1
tps = ["3V3A", "GND", "VREF", "VTH_ON", "VTH_OFF", "LED_EN"] + \
      [f"VPHOTO_{x}" for x in CH] + [f"VEVENT_{x}" for x in CH] + \
      [f"RAW_{p}_{x}" for x in CH for p in ("ON", "OFF")]
for n in tps:
    add("TP", "Connector:TestPoint", n, "TestPoint:TestPoint_Pad_D1.0mm", {"1": n}, "Test pads", f"Probe pad {n}")
for side in ("L", "R"):
    add("H", "Mechanical:MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2", {}, "Mechanical",
        f"M12 lens holder screw ({side})")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"title": "Neuromorphic IR Event Sensor - Rev A-C (compact)", "revision": "A-C",
               "notes": __doc__.strip(), "power_flags": "auto", "parts": parts}, f, indent=1)
print(f"{len(parts)} parts -> {os.path.abspath(OUT)}")
