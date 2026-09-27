"""Minimal KiCad S-expression reader/writer used by the headless generators."""
import re

KICAD = r"C:\Program Files\KiCad\10.0"
SYMDIR = KICAD + r"\share\kicad\symbols"
FPDIR = KICAD + r"\share\kicad\footprints"

_tok = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')


class Sym(str):
    """Unquoted atom."""


def parse(text):
    stack, cur = [], []
    pos = 0
    n = len(text)
    while pos < n:
        m = _tok.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError("parse error at %d" % pos)
        pos = m.end()
        if m.group(1):
            stack.append(cur)
            cur = []
        elif m.group(2):
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif m.group(3) is not None:
            cur.append(re.sub(r'\\(.)', lambda g: "\n" if g.group(1) == "n" else g.group(1),
                              m.group(3)))
        elif m.group(4) is not None:
            cur.append(Sym(m.group(4)))
    return cur[0] if len(cur) == 1 else cur


def dump(e, indent=0):
    if isinstance(e, list):
        if not e:
            return "()"
        simple = all(not isinstance(x, list) for x in e)
        if simple:
            return "(" + " ".join(dump(x) for x in e) + ")"
        out = "(" + dump(e[0])
        for x in e[1:]:
            if isinstance(x, list):
                out += "\n" + "\t" * (indent + 1) + dump(x, indent + 1)
            else:
                out += " " + dump(x)
        return out + "\n" + "\t" * indent + ")"
    if isinstance(e, Sym):
        return str(e)
    if isinstance(e, bool):
        return "yes" if e else "no"
    if isinstance(e, (int, float)):
        s = ("%.4f" % e).rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    return '"' + str(e).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def find(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]


def find1(e, key):
    r = find(e, key)
    return r[0] if r else None


_libcache = {}


def load_lib(lib):
    if lib not in _libcache:
        with open(SYMDIR + "\\" + lib + ".kicad_sym", encoding="utf-8") as f:
            _libcache[lib] = parse(f.read())
    return _libcache[lib]


def get_symbol(lib_id):
    """Return a fully resolved (extends flattened) symbol definition named lib_id."""
    lib, name = lib_id.split(":")
    tree = load_lib(lib)
    syms = {s[1]: s for s in find(tree, "symbol")}
    s = syms[name]
    ext = find1(s, "extends")
    if ext:
        base = syms[ext[1]]
        new = [Sym("symbol"), name]
        # properties from derived, graphics/pins from base
        props = {p[1]: p for p in find(s, "property")}
        for item in base[2:]:
            if isinstance(item, list) and item[0] == "property" and item[1] in props:
                new.append(props.pop(item[1]))
            elif isinstance(item, list) and item[0] == "symbol":
                sub = list(item)
                sub[1] = sub[1].replace(ext[1], name, 1)
                new.append(sub)
            else:
                new.append(item)
        for p in props.values():
            new.append(p)
        for item in s[2:]:
            if isinstance(item, list) and item[0] not in ("property", "extends", "symbol"):
                if not find1(new, item[0]):
                    new.append(item)
        s = new
    out = list(s)
    out[1] = lib_id
    return out


def symbol_pins(sym):
    """Return list of dict(number,name,x,y,angle,unit,type) in symbol coordinates (y up)."""
    pins = []
    for sub in find(sym, "symbol"):
        m = re.search(r"_(\d+)_(\d+)$", sub[1])
        unit = int(m.group(1)) if m else 0
        for p in find(sub, "pin"):
            at = find1(p, "at")
            pins.append(dict(
                number=find1(p, "number")[1], name=find1(p, "name")[1],
                x=float(at[1]), y=float(at[2]), angle=float(at[3]) if len(at) > 3 else 0.0,
                length=float(find1(p, "length")[1]), unit=unit, type=str(p[1]),
                hidden=any(x == "hide" or (isinstance(x, list) and x[0] == "hide") for x in p)))
    return pins
