"""Neuromorphic IR Event Sensor - Rev A-THT (all through-hole, hand-assemblable).

Single source of truth for the netlist. gen_schematic.py turns this into the
KiCad schematic; the PCB is then populated from the schematic netlist.

Deviations from docs/DESIGN_SPECIFICATION.md (SMD Rev A), forced by THT availability:
  OPA381 (MSOP)         -> MCP6022 dual CMOS RRIO op-amp, DIP-8 (2 pcs)
  TLV3202 (SOIC)        -> MCP6542 dual push-pull comparator, DIP-8 (4 pcs)
  74LVC1G123 x8         -> 74HC123 dual retriggerable monostable, DIP-16 (4 pcs)
  REF3312 1.25 V        -> LM385BZ-1.2 1.235 V shunt reference, TO-92
  AO3400A               -> PN2222A NPN, TO-92, 1k base resistor
  VBPW34FASR            -> OSRAM BPW 34 F (THT DIL, daylight filter)
  0603/1206 passives    -> axial resistors, radial ceramic/electrolytic capacitors
"""

# ---------------------------------------------------------------- footprints
FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_C = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"
FP_CP = "Capacitor_THT:CP_Radial_D5.0mm_P2.00mm"
FP_DIP8 = "Package_DIP:DIP-8_W7.62mm_Socket"
FP_DIP16 = "Package_DIP:DIP-16_W7.62mm_Socket"
FP_TO92 = "Package_TO_SOT_THT:TO-92_Inline_Wide"
FP_PD = "OptoDevice:Osram_DIL2_4.3x4.65mm_P5.08mm"
FP_LED = "LED_THT:LED_D5.0mm_IRGrey"
FP_FB = "Inductor_THT:L_Axial_L5.3mm_D2.2mm_P7.62mm_Horizontal_Vishay_IM-1"
FP_IDC10 = "Connector_IDC:IDC-Header_2x05_P2.54mm_Vertical"
FP_HDR = "Connector_PinHeader_2.54mm:PinHeader_1x%02d_P2.54mm_Vertical"
FP_TP = "TestPoint:TestPoint_Keystone_5000-5004_Miniature"
FP_MH = "MountingHole:MountingHole_3.2mm_M3"

CH = ["TL", "TR", "BL", "BR"]

parts = []      # dict(ref, lib, value, fp, units={unit: {pin: net}}, fields={}, dnp, group)
_count = {}


def _next(prefix):
    _count[prefix] = _count.get(prefix, 0) + 1
    return "%s%d" % (prefix, _count[prefix])


def add(prefix, lib, value, fp, pins, group, desc="", mpn="", dnp=False, ref=None, units=None):
    ref = ref or _next(prefix)
    parts.append(dict(ref=ref, lib=lib, value=value, fp=fp,
                      units=units if units is not None else {1: pins},
                      desc=desc, mpn=mpn, dnp=dnp, group=group))
    return ref


def R(value, a, b, group, desc="", mpn="", dnp=False):
    return add("R", "Device:R", value, FP_R, {"1": a, "2": b}, group, desc, mpn, dnp)


def C(value, a, b, group, desc="", mpn=""):
    return add("C", "Device:C", value, FP_C, {"1": a, "2": b}, group, desc, mpn)


def CP(value, pos, neg, group, desc=""):
    return add("C", "Device:C_Polarized", value, FP_CP, {"1": pos, "2": neg}, group, desc,
               "10uF 16V radial electrolytic")


# ---------------------------------------------------------------- power / reference
G = "Power & Reference"
add("FB", "Device:FerriteBead", "600R@100MHz", FP_FB, {"1": "3V3", "2": "3V3A"}, G,
    "Analog rail filter bead", "Axial ferrite bead (e.g. Fair-Rite 2743001112)")
CP("10uF", "3V3A", "GND", G, "Analog bulk")
CP("10uF", "3V3", "GND", G, "Logic / one-shot bulk")
add("U", "Reference_Voltage:LM385BZ-1.2", "LM385BZ-1.2", FP_TO92,
    {"2": "VREF", "3": "GND"}, G, "1.235 V shunt reference (VREF)", "LM385BZ-1.2", ref="U1")
R("4.7k", "3V3A", "VREF", G, "Reference bias ~0.44 mA")
C("1uF", "VREF", "GND", G, "Reference decoupling", "1uF X7R radial")
C("100nF", "VREF", "GND", G, "Reference decoupling")
# thresholds (0.1 %)
R("499k 0.1%", "3V3A", "VTH_ON", G, "ON threshold upper")
R("10k 0.1%", "VTH_ON", "VREF", G, "ON threshold lower")
R("10k 0.1%", "VREF", "VTH_OFF", G, "OFF threshold upper")
R("301k 0.1%", "VTH_OFF", "GND", G, "OFF threshold lower")
C("100nF", "VTH_ON", "GND", G, "Threshold filter")
C("100nF", "VTH_OFF", "GND", G, "Threshold filter")

# ---------------------------------------------------------------- TIAs
_count["U"] = 1
tia = {}
for pair in (("TL", "BL"), ("TR", "BR")):
    u = _next("U")
    units = {}
    for unit, x, pins in ((1, pair[0], ("3", "2", "1")), (2, pair[1], ("5", "6", "7"))):
        units[unit] = {pins[0]: "VREF", pins[1]: "TIA_IN_" + x, pins[2]: "VPHOTO_" + x}
        tia[x] = u
    units[3] = {"8": "3V3A", "4": "GND"}
    add("U", "Amplifier_Operational:MCP6022", "MCP6022", FP_DIP8, None,
        "TIA", "Dual RRIO CMOS op-amp (TIA)", "MCP6022-I/P", ref=u, units=units)
    C("100nF", "3V3A", "GND", "TIA", "%s decoupling" % u)

for i, x in enumerate(CH):
    g = "Channel " + x
    add("D", "Sensor_Optical:BPW34", "BPW34F", FP_PD, {"1": "TIA_IN_" + x, "2": "GND"}, g,
        "IR photodiode %s (cathode to TIA input)" % x,
        "ams OSRAM BPW 34 F (THT, daylight filter); alt Vishay BPW34")
    R("18k 0.1%", "TIA_IN_" + x, "VPHOTO_" + x, g, "TIA feedback RF")
    C("47pF C0G", "TIA_IN_" + x, "VPHOTO_" + x, g, "TIA feedback CF", "47pF C0G radial")
    C("100nF", "VPHOTO_" + x, "VEVENT_" + x, g, "Adaptation CA (swap 47n/220n)")
    R("22k", "VEVENT_" + x, "VREF", g, "Adaptation RA (swap 10k/47k)")
    R("100", "VPHOTO_" + x, "VPHOTO_%s_DBG" % x, g, "Debug header series R")

# ---------------------------------------------------------------- comparators
for x in CH:
    g = "Channel " + x
    u = _next("U")
    units = {1: {"3": "VEVENT_" + x, "2": "VTH_ON", "1": "RAW_ON_" + x},
             2: {"5": "VTH_OFF", "6": "VEVENT_" + x, "7": "RAW_OFF_" + x},
             3: {"8": "3V3A", "4": "GND"}}
    add("U", "Comparator:MCP6562", "MCP6542", FP_DIP8, None, g,
        "Dual push-pull comparator, ON (A) / OFF (B)", "MCP6542-I/P", ref=u, units=units)
    C("100nF", "3V3A", "GND", g, "%s decoupling" % u)
    R("1M", "RAW_ON_" + x, "VEVENT_" + x, g, "Optional ON hysteresis (DNP)", dnp=True)

# ---------------------------------------------------------------- one-shots
for x in CH:
    g = "One-shot " + x
    u = _next("U")
    units = {
        1: {"1": "GND", "2": "RAW_ON_" + x, "3": "3V3", "14": "CX_ON_" + x,
            "15": "RC_ON_" + x, "13": "Q_ON_" + x, "4": None},
        2: {"9": "GND", "10": "RAW_OFF_" + x, "11": "3V3", "6": "CX_OFF_" + x,
            "7": "RC_OFF_" + x, "5": "Q_OFF_" + x, "12": None},
        3: {"16": "3V3", "8": "GND"}}
    add("U", "74xx:74HC123", "74HC123", FP_DIP16, None, g,
        "Dual retriggerable monostable, ON (A) / OFF (B)", "74HC123 (SN74HC123N / 74HC123N)",
        ref=u, units=units)
    C("100nF", "3V3", "GND", g, "%s decoupling" % u)
    for pol in ("ON", "OFF"):
        C("12nF C0G", "CX_%s_%s" % (pol, x), "RC_%s_%s" % (pol, x), g, "One-shot timing C",
          "12nF C0G radial or film")
        R("18k", "RC_%s_%s" % (pol, x), "3V3", g, "One-shot timing R (~100 us)")
        R("150", "Q_%s_%s" % (pol, x), "SPIKE_%s_%s" % (pol, x), g, "Spike series R")

# ---------------------------------------------------------------- IR LED driver
G = "IR illumination"
add("LED", "Device:LED", "TSAL6200", FP_LED, {"1": "LED_K", "2": "LED_A"}, G,
    "940 nm IR emitter", "Vishay TSAL6200")
R("82", "3V3", "LED_A", G, "LED current (~22 mA) - tuning 68/100/150")
add("Q", "Transistor_BJT:PN2222A", "PN2222A", FP_TO92,
    {"1": "GND", "2": "Q_B", "3": "LED_K"}, G, "LED low-side switch", "PN2222A")
R("1k", "LED_EN", "Q_B", G, "Base resistor")
R("100k", "LED_EN", "GND", G, "LED_EN pulldown")
CP("10uF", "3V3", "GND", G, "LED local bulk")

# ---------------------------------------------------------------- connectors
G = "Connectors"
j1 = {"1": "GND", "2": "3V3"}
for i, x in enumerate(CH):
    j1[str(3 + 2 * i)] = "SPIKE_ON_" + x
    j1[str(4 + 2 * i)] = "SPIKE_OFF_" + x
add("J", "Connector_Generic:Conn_02x05_Odd_Even", "FPGA", FP_IDC10, j1, G,
    "Keyed 2x5 event header to Tang Nano 20K", "2x5 2.54mm shrouded box header")
add("J", "Connector_Generic:Conn_01x06", "DEBUG", FP_HDR % 6,
    {"1": "GND", "2": "VREF", "3": "VPHOTO_TL_DBG", "4": "VPHOTO_TR_DBG",
     "5": "VPHOTO_BL_DBG", "6": "VPHOTO_BR_DBG"}, G, "Analog debug header")
add("J", "Connector_Generic:Conn_01x03", "LED_EN", FP_HDR % 3,
    {"1": "3V3", "2": "LED_EN", "3": "GND"}, G,
    "Jumper 1-2 = LED on, 2-3 = off, or drive pin 2 from FPGA")
j4 = {"1": "GND"}
for i, x in enumerate(CH):
    j4[str(2 + 2 * i)] = "RAW_ON_" + x
    j4[str(3 + 2 * i)] = "RAW_OFF_" + x
add("J", "Connector_Generic:Conn_01x09", "RAW_PROBE", FP_HDR % 9, j4, G,
    "Raw comparator probe header")
j5 = {"1": "GND", "2": "3V3", "3": "3V3A", "4": "VREF", "5": "VTH_ON", "6": "VTH_OFF"}
for i, x in enumerate(CH):
    j5[str(7 + i)] = "VEVENT_" + x
add("J", "Connector_Generic:Conn_01x10", "EVENT_PROBE", FP_HDR % 10, j5, G,
    "Rail / threshold / event-node probe header")
add("TP", "Connector:TestPoint", "GND", FP_TP, {"1": "GND"}, G, "Scope ground loop")
add("TP", "Connector:TestPoint", "GND", FP_TP, {"1": "GND"}, G, "Scope ground loop")
for _ in range(4):
    add("H", "Mechanical:MountingHole", "M3", FP_MH, {}, G, "M3 mounting hole")

# power flags
for net in ("3V3", "3V3A", "GND"):
    add("#FLG", "power:PWR_FLAG", "PWR_FLAG", "", {"1": net}, "Power & Reference")
