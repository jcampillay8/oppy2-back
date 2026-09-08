# src/learning_analysis/services/ielts_syllabus.py
import os
import glob
from typing import Dict, Any, List, Optional

POSSIBLE_DIRS = [
    "/app/English-IELTS",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../English-IELTS")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../English-IELTS")),
]

BASE_IELTS_DIR = next((d for d in POSSIBLE_DIRS if os.path.exists(d)), POSSIBLE_DIRS[0])

LEVEL_TITLES = {
    1: {"title": "Nouns (Sustantivos)", "cefr": "A1-B1"},
    2: {"title": "Pronouns (Pronombres)", "cefr": "A1-B1"},
    3: {"title": "Verbs & Tenses (Verbos y Tiempos)", "cefr": "A1-B2"},
    4: {"title": "Sentence Parts (Sujeto, Predicado, Objeto)", "cefr": "A2-B1"},
    5: {"title": "Adjectives (Adjetivos y Comparativos)", "cefr": "A2-B2"},
    6: {"title": "Adverbs (Adverbios y Frases Adverbiales)", "cefr": "A2-B2"},
    7: {"title": "Prepositions (Preposiciones)", "cefr": "A2-B2"},
    8: {"title": "Conjunctions (Conjunciones y Conectores)", "cefr": "B1-B2"},
    9: {"title": "Verbals (Gerundios, Participios, Infinitivos)", "cefr": "B2-C1"},
    10: {"title": "Clauses (Cláusulas Dependientes e Independientes)", "cefr": "B2-C1"},
    11: {"title": "Sentences (Estructura de Oraciones Avanzadas)", "cefr": "B2-C2"},
}

_cached_syllabus: Optional[Dict[int, Any]] = None

def load_ielts_syllabus() -> Dict[int, Any]:
    global _cached_syllabus
    if _cached_syllabus is not None:
        return _cached_syllabus

    base_dir = next((d for d in POSSIBLE_DIRS if os.path.exists(d)), None)
    syllabus: Dict[int, Any] = {}
    if not base_dir or not os.path.exists(base_dir):
        print(f"[ERROR] English-IELTS directory not found in: {POSSIBLE_DIRS}")
        return syllabus

    dirs = sorted([d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))])

    for idx, d in enumerate(dirs, 1):
        if idx > 11:
            break
        level_dir = os.path.join(base_dir, d)
        md_files = sorted(glob.glob(os.path.join(level_dir, "**/*.md"), recursive=True))

        meta = LEVEL_TITLES.get(idx, {"title": d, "cefr": "B1-B2"})
        units_map: Dict[int, Dict[str, str]] = {}

        for unit_idx, fpath in enumerate(md_files, 1):
            title = _extract_title_from_file(fpath)
            rel_path = os.path.relpath(fpath, base_dir)
            units_map[unit_idx] = {
                "title": title,
                "file_path": rel_path,
                "abs_path": fpath
            }

        syllabus[idx] = {
            "level": idx,
            "title": meta["title"],
            "cefr": meta["cefr"],
            "units": units_map
        }

    _cached_syllabus = syllabus
    return syllabus

def _extract_title_from_file(fpath: str) -> str:
    try:
        with open(fpath, "r", encoding="utf-8") as fp:
            for line in fp:
                line_str = line.strip()
                if line_str.startswith("# "):
                    title = line_str.replace("# ", "").strip()
                    for prefix in ["📚 English Grammar — ", "IELTS Grammar 101 by IOT"]:
                        if title.startswith(prefix):
                            title = title.replace(prefix, "")
                    return title
    except Exception:
        pass
    basename = os.path.basename(fpath).replace(".md", "")
    return basename.replace("-", " ").title()

def get_ielts_unit_info(level: int, unit: int) -> Optional[Dict[str, str]]:
    syllabus = load_ielts_syllabus()
    level_data = syllabus.get(level)
    if not level_data:
        return None
    return level_data["units"].get(unit)

def get_ielts_unit_markdown(level: int, unit: int) -> Optional[str]:
    unit_info = get_ielts_unit_info(level, unit)
    if not unit_info or not os.path.exists(unit_info["abs_path"]):
        return None
    with open(unit_info["abs_path"], "r", encoding="utf-8") as fp:
        return fp.read()
