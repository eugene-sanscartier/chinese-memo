import json
import sys
from collections import defaultdict
from pathlib import Path

from hanzipy.dictionary import HanziDictionary

ROOT_DIR = Path(__file__).resolve().parents[2]
COMPONENTS_PATH = ROOT_DIR / "data" / "derived" / "components" / "components.json"
GLOSS_PATH = ROOT_DIR / "data" / "source" / "authored" / "gloss.json"
DICTIONARY_CHAR_PATH = ROOT_DIR / "data" / "source" / "reference" / "dictionary_char.jsonl"
CACHE_DIR = ROOT_DIR / "data" / "cache" / "component_gloss_translation"
MISSING_GLOSS_PATH = CACHE_DIR / "missing_gloss.json"
TRANSLATED_GLOSS_PATH = CACHE_DIR / "missing_gloss_translated.json"
SUMMARY_PATH = CACHE_DIR / "summary.json"
HANZIPY_RADICALS_PATH = Path("/home/eugene/.venv/venv/lib/python3.14/site-packages/hanzipy/data/radical_with_meanings.json")
ONLINE_GLOSS_OVERRIDES = {
    "⺳": "net",
    "㳟": "respectful",
    "弚": "younger brother",
    "旲": "sunlight",
    "洰": "ditch",
    "茾": "herb",
    "迶": "walking",
    "龵": "hand",
}
PACKAGE_GLOSS_OVERRIDES = {
    "倠": "bird",
    "厈": "cliff",
    "厽": "star",
    "圡": "earth",
    "圤": "clod",
    "圼": "mud",
    "巸": "broad",
    "汒": "vast",
    "犾": "dogs biting",
    "疌": "rapid",
    "豙": "enraged boar",
    "遀": "follow",
    "龴": "private, selfish",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as file_obj: return json.load(file_obj)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file_obj: json.dump(data, file_obj, ensure_ascii=False, indent=2)


def load_dictionary_char():
    rows = {}
    with open(DICTIONARY_CHAR_PATH, "r", encoding="utf-8") as file_obj:
        for line in file_obj:
            if not line.strip(): continue
            row = json.loads(line)
            if row.get("char") not in rows: rows[row.get("char")] = row
    return rows


def load_hanzipy_radicals():
    with open(HANZIPY_RADICALS_PATH, "r", encoding="utf-8") as file_obj: return json.load(file_obj)


def get_hanzipy_gloss(component, dictionary, radicals):
    if component in radicals: return radicals[component]
    try:
        entries = dictionary.definition_lookup(component)
    except Exception:
        return ""
    if not entries: return ""
    return entries[0].get("definition", "").split("/")[0].strip()


def build_records():
    components_map = load_json(COMPONENTS_PATH)
    gloss = load_json(GLOSS_PATH)
    dictionary_char = load_dictionary_char()
    hanzipy_dictionary = HanziDictionary()
    hanzipy_radicals = load_hanzipy_radicals()
    unique_components = sorted({component for components in components_map.values() for component in components})
    hosts = defaultdict(list)
    for char, components in components_map.items():
        for component in components:
            if char not in hosts[component]: hosts[component] += [char]
    missing_gloss = {}
    for component in unique_components:
        if component in gloss: continue
        dict_gloss = dictionary_char.get(component, {}).get("gloss", "")
        if not dict_gloss: dict_gloss = get_hanzipy_gloss(component, hanzipy_dictionary, hanzipy_radicals)
        if not dict_gloss: dict_gloss = PACKAGE_GLOSS_OVERRIDES.get(component, "")
        if component in ONLINE_GLOSS_OVERRIDES: dict_gloss = ONLINE_GLOSS_OVERRIDES[component]
        missing_gloss[component] = {"gloss_en": dict_gloss, "gloss_fr": "", "example_characters": hosts[component]}
    summary = {
        "unique_components": len(unique_components),
        "covered_by_gloss": sum(1 for component in unique_components if component in gloss),
        "missing_gloss_total": len(missing_gloss),
        "missing_fr_translation": sum(1 for gloss in missing_gloss.values() if gloss["gloss_en"]),
        "missing_en_gloss": sum(1 for gloss in missing_gloss.values() if not gloss["gloss_en"]),
    }
    return missing_gloss, summary


def build():
    missing_gloss, summary = build_records()
    write_json(MISSING_GLOSS_PATH, missing_gloss)
    write_json(SUMMARY_PATH, summary)
    print(f"missing_gloss.json: {len(missing_gloss)} entries")


def translate_google():
    from google_translation import translate_texts
    missing_gloss = load_json(MISSING_GLOSS_PATH)
    components = [component for component, gloss in missing_gloss.items() if gloss.get("gloss_en")]
    en_glosses = [missing_gloss[component]["gloss_en"] for component in components]
    fr_glosses = translate_texts(en_glosses) if en_glosses else []
    translated = {}
    for component, gloss_fr in zip(components, fr_glosses):
        translated[component] = {"gloss_en": missing_gloss[component]["gloss_en"], "gloss_fr": gloss_fr, "example_characters": missing_gloss[component]["example_characters"]}
    write_json(TRANSLATED_GLOSS_PATH, translated)
    print(f"missing_gloss_translated.json: {len(translated)} entries")


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "build"
    if command == "build": build(); return
    if command == "google": translate_google(); return
    raise SystemExit("usage: component_gloss.py [build|google]")


if __name__ == "__main__":
    main()
