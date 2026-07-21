#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
TEMPLATE_PATH = SCRIPT_DIR / "template.html"
OUT_DIR = Path("/home/boc/Proiecte/admitere_master/exam_prep")
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(SCRIPT_DIR))
from enunt_format import render_enunt_html

template = TEMPLATE_PATH.read_text(encoding="utf-8")

SPECIAL_LABELS = {
    "all_cpp": "Toate întrebările C/C++",
    "all_sql": "Toate întrebările SQL/PL-SQL/Baze de date",
}


def display_label(stem):
    if stem in SPECIAL_LABELS:
        return SPECIAL_LABELS[stem]
    m = re.match(r"test(\d+)$", stem)
    if m:
        return f"Test de simulare {m.group(1)}"
    return stem


years = sorted(p.stem for p in DATA_DIR.glob("*.json"))
year_summaries = []

for year in years:
    data = json.loads((DATA_DIR / f"{year}.json").read_text(encoding="utf-8"))
    questions = data["questions"]
    for q in questions:
        q["enunt_html"] = render_enunt_html(q["enunt"])
    label = display_label(year)
    payload = {
        "year": year,
        "sursa": data["header"].get("sursa", ""),
        "punctaj": data["header"].get("punctaj", ""),
        "questions": questions,
    }
    data_json = json.dumps(payload, ensure_ascii=False)
    data_json = data_json.replace("</script", "<\\/script")

    html = template
    html = html.replace("__DATA_JSON__", data_json)
    html = html.replace("__YEAR__", label)
    html = html.replace("__SURSA__", payload["sursa"])
    html = html.replace("__PUNCTAJ__", payload["punctaj"])
    html = html.replace("__QCOUNT__", str(len(questions)))

    out_path = OUT_DIR / f"{year}.html"
    out_path.write_text(html, encoding="utf-8")

    n_err = sum(1 for q in questions if q["status_verificare"] == "EROARE_BAREM")
    cats = {}
    for q in questions:
        cats[q["categorie"]] = cats.get(q["categorie"], 0) + 1
    year_summaries.append({
        "year": year, "count": len(questions), "eroare_barem": n_err, "categorii": cats,
    })
    print(f"{year}: scris {out_path} ({len(questions)} intrebari, {n_err} erori barem)")

(SCRIPT_DIR / "year_summaries.json").write_text(json.dumps(year_summaries, ensure_ascii=False, indent=2), encoding="utf-8")
