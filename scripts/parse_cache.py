#!/usr/bin/env python3
"""Parseaza fisierele cache/<an>.txt in structuri JSON pentru generarea paginilor HTML."""
import json
import re
import sys
from pathlib import Path

CACHE_DIR = Path("/home/boc/Proiecte/admitere_master/cache")
OUT_DIR = Path("/home/boc/Proiecte/admitere_master/scripts/data")
OUT_DIR.mkdir(parents=True, exist_ok=True)

Q_RE = re.compile(r"^##### ÎNTREBAREA (\d+) #####\s*$")
FIELD_RE = re.compile(r"^(CATEGORIE|RASPUNS_BAREM|RASPUNS_CORECT|STATUS_VERIFICARE):\s*(.*)$")
OPT_RE = re.compile(r"^([a-d])\)\s?(.*)$")


def parse_file(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")

    header = {}
    for line in lines[:6]:
        if line.startswith("Sursă:"):
            header["sursa"] = line.split(":", 1)[1].strip()
        elif line.startswith("Format sursă original:"):
            header["format_sursa"] = line.split(":", 1)[1].strip()
        elif line.startswith("Punctaj:"):
            header["punctaj"] = line.split(":", 1)[1].strip()

    blocks = []
    current = []
    cur_num = None
    for line in lines:
        m = Q_RE.match(line)
        if m:
            if cur_num is not None:
                blocks.append((cur_num, current))
            cur_num = int(m.group(1))
            current = []
        else:
            current.append(line)
    if cur_num is not None:
        blocks.append((cur_num, current))

    questions = []
    for num, block in blocks:
        state = None
        categorie = None
        enunt_lines = []
        variante = {}
        raspuns_barem = None
        raspuns_corect = None
        status = None
        explicatie_lines = []

        for line in block:
            fm = FIELD_RE.match(line)
            om = OPT_RE.match(line)
            if fm:
                key, val = fm.group(1), fm.group(2).strip()
                if key == "CATEGORIE":
                    categorie = val
                    state = None
                elif key == "RASPUNS_BAREM":
                    raspuns_barem = val
                    state = None
                elif key == "RASPUNS_CORECT":
                    raspuns_corect = val
                    state = None
                elif key == "STATUS_VERIFICARE":
                    status = val
                    state = None
                continue
            if line.strip() == "ENUNT:":
                state = "enunt"
                continue
            if line.strip() == "VARIANTE:":
                state = "variante"
                continue
            if line.strip() == "EXPLICATIE:" or line.startswith("EXPLICATIE:"):
                state = "explicatie"
                rest = line[len("EXPLICATIE:"):].strip()
                if rest:
                    explicatie_lines.append(rest)
                continue
            if state == "enunt":
                enunt_lines.append(line)
            elif state == "variante":
                if om:
                    variante[om.group(1)] = om.group(2)
                elif line.strip() == "":
                    continue
                else:
                    last_key = list(variante.keys())[-1] if variante else None
                    if last_key:
                        variante[last_key] += " " + line.strip()
            elif state == "explicatie":
                explicatie_lines.append(line)

        while enunt_lines and enunt_lines[0].strip() == "":
            enunt_lines.pop(0)
        while enunt_lines and enunt_lines[-1].strip() == "":
            enunt_lines.pop()
        while explicatie_lines and explicatie_lines[-1].strip() == "":
            explicatie_lines.pop()

        questions.append({
            "nr": num,
            "categorie": categorie,
            "enunt": "\n".join(enunt_lines),
            "variante": variante,
            "raspuns_barem": raspuns_barem,
            "raspuns_corect": raspuns_corect,
            "status_verificare": status,
            "explicatie": "\n".join(explicatie_lines),
        })

    return {"header": header, "questions": questions}


def main():
    summary = {}
    for path in sorted(CACHE_DIR.glob("*.txt")):
        year = path.stem
        data = parse_file(path)
        n = len(data["questions"])
        missing = [q["nr"] for q in data["questions"] if not q["variante"] or len(q["variante"]) != 4 or not q["raspuns_corect"]]
        summary[year] = {"count": n, "missing_or_bad": missing}
        out_path = OUT_DIR / f"{year}.json"
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{year}: {n} intrebari -> {out_path}" + (f"  !! PROBLEME: {missing}" if missing else ""))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
