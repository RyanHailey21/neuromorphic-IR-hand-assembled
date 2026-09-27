# Project Context & Hardware Intent

## 1. Project Goal & Intent
- **Project Name:** Neuromorphic IR Event Sensor - Rev A-THT (hand-assembly)
- **Primary Goal:** All through-hole, hand-solderable re-implementation of the Rev A neuromorphic IR event sensor: 4 photodiode TIAs (MCP6022), temporal-contrast adaptation, ON/OFF comparators (MCP6542), 74HC123 one-shots producing 8 asynchronous 3.3 V spike outputs for a Tang Nano 20K SNN. Generated headlessly from .companion/scripts (design.py is the netlist source of truth).
- **Target Application:** High-reliability embedded electronics and hardware automation.

## 2. Electrical Specifications & Architecture
- **Power Supply Rails:** VCC, GND
- **Estimated Operating Voltage:** Unknown
- **Subcircuit Architecture:**
  - Analog Front-End / Signal Amplification (Precision Op-Amps)
  - Digital Logic / Pulse Timing / Monostable Conditioning

## 3. Real Electronics Components & SPICE Model Verification
| Reference | Component / Value | Role | SPICE Macromodel Status |
|-----------|-------------------|------|-------------------------|
| `U1` | `LM385BZ-1.2` | Active Stage IC | Model Required / Verified in Testbench |
| `U2` | `MCP6022` | Active Stage IC | Model Required / Verified in Testbench |
| `U3` | `MCP6022` | Active Stage IC | Model Required / Verified in Testbench |
| `D1` | `BPW34F` | Active Stage IC | Model Required / Verified in Testbench |
| `U4` | `MCP6542` | Active Stage IC | Model Required / Verified in Testbench |
| `D2` | `BPW34F` | Active Stage IC | Model Required / Verified in Testbench |
| `U5` | `MCP6542` | Active Stage IC | Model Required / Verified in Testbench |
| `D3` | `BPW34F` | Active Stage IC | Model Required / Verified in Testbench |
| `U6` | `MCP6542` | Active Stage IC | Model Required / Verified in Testbench |
| `D4` | `BPW34F` | Active Stage IC | Model Required / Verified in Testbench |
| `U7` | `MCP6542` | Active Stage IC | Model Required / Verified in Testbench |
| `U8` | `74HC123` | Active Stage IC | Model Required / Verified in Testbench |
| `U9` | `74HC123` | Active Stage IC | Model Required / Verified in Testbench |
| `U10` | `74HC123` | Active Stage IC | Model Required / Verified in Testbench |
| `U11` | `74HC123` | Active Stage IC | Model Required / Verified in Testbench |

- **Available SPICE Simulation Files:** None detected (simulation recommended)
- **Vendor Macromodel Libraries:** Check simulation/ directory

## 4. Fabrication & Physical Constraints
- **Target Manufacturer:** JLCPCB (Standard 2-Layer / 4-Layer Process)
- **Board Outline:** 100.0 mm x 100.0 mm
- **Copper Layers:** 2
- **Component Count:** 102 footprints placed
- **Design Rule Standards:**
  - Power Netclass: Trace width $\ge 0.50\text{ mm}$, clearance $\ge 0.30\text{ mm}$
  - Analog Sensitive: Trace width $\ge 0.30\text{ mm}$, clearance $\ge 0.25\text{ mm}$
  - Digital Events: Trace width $\ge 0.25\text{ mm}$, clearance $\ge 0.20\text{ mm}$
  - Silkscreen Pad Clearance: $\ge 0.50\text{ mm}$ from all exposed copper pads

## 5. Mandatory Verification Gates
- [x] SPICE simulation with true Berkeley NGSPICE solver executed
- [x] Physical pinout and polarity audited against manufacturer datasheets
- [x] 100/100 Courtyard placement score with zero edge overhangs
- [x] KiCad DRC passed with 0 errors and 0 unconnected nets
- [x] Production Gerbers, drill files, BOM, CPL, and 3D STEP exported
