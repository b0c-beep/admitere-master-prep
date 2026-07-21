#!/usr/bin/env python3
"""Agrega intrebarile din toate cele 17 surse (ani + teste de simulare) in
seturi tematice combinate: toate C/C++ intr-un set, toate SQL+PL/SQL+Baze de
date (teorie) in alt set. Fiecare intrebare primeste un tag 'sursa' cu originea
(anul sau numarul testului) pentru context, si e renumerotata secvential."""
import json
import re
from pathlib import Path

DATA_DIR = Path("/home/boc/Proiecte/admitere_master/scripts/data")


def source_label(stem):
    m = re.match(r"test(\d+)$", stem)
    if m:
        return f"Test {m.group(1)}"
    return stem


def collect(categories, out_id, title_sursa):
    items = []
    for f in sorted(DATA_DIR.glob("*.json")):
        stem = f.stem
        if stem.startswith("all_"):
            continue  # nu re-agrega din seturile combinate deja generate
        d = json.loads(f.read_text(encoding="utf-8"))
        label = source_label(stem)
        for q in d["questions"]:
            if q["categorie"] in categories:
                qq = dict(q)
                qq["sursa_tag"] = label
                items.append(qq)
    for i, q in enumerate(items, start=1):
        q["nr"] = i
    payload = {
        "header": {
            "sursa": title_sursa,
            "punctaj": f"3 puncte/întrebare corectă, {len(items)} întrebări în total",
        },
        "questions": items,
    }
    out_path = DATA_DIR / f"{out_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{out_id}: {len(items)} intrebari -> {out_path}")


collect(
    {"C/C++"},
    "all_cpp",
    "Toate întrebările C/C++ din anii 2019–2025 și testele de simulare 1–10",
)
collect(
    {"SQL", "PL/SQL", "Baze de date (teorie)"},
    "all_sql",
    "Toate întrebările SQL, PL/SQL și Baze de date din anii 2019–2025 și testele de simulare 1–10",
)
