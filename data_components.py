import json
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
REFERENCE_DIR = DATA_DIR / "source" / "reference"
MEMODEVICE_DIR = DATA_DIR / "derived" / "memodevice"

NOISE = set('一丨丶丿乙亅㇆㇉㇠㇇㇒㇗㇈㇏㇖㇗𠂇𠂉⺁⺙⺮⺈⺌⻊⺊⺹⻎') | {'No glyph available'}
_RADICAL_NORM = {'⻖': '阝', '⻏': '阝', '⺼': '月', '辶': '⻌'}
_COMPONENT_REMAP = {'⺌': '小', '⺮': '竹', '𧾷': '足', '𤣩': '王', '礻': '示', '牜': '牛', '𠆢': '人', '𫩠': '尚', '龸': '尚', '&CDP-8958;': '月'}
_SELF_COMPONENT_OVERRIDES = {'众', '森', '晶'}
# Explicit host-character repairs for opaque/CDP families. Each entry records the
# learner-facing replacement chosen for that specific character, not a global
# entity->character rule.
_CHAR_COMPONENT_OVERRIDES = {
    '师': ['刂', '帀'], '归': ['刂', '彐'], '帅': ['刂', '巾'],
    '候': ['亻', '矦'], '侯': ['亻', '矦'],
    '留': ['卯', '田'], '贸': ['卯', '贝'],
    '即': ['皀', '卩'], '既': ['皀', '旡'],
    '辨': ['辡', '刂'], '班': ['玨', '刂'],
    '介': ['人', '八'], '养': ['羊', '介'], '乔': ['夭', '八'],
    '农': ['农'], '丧': ['丧'], '畏': ['畏'],
    '产': ['产'], '商': ['立', '冏'],
    '受': ['爫', '又'], '爱': ['冖', '友'],
    '帝': ['立', '巾'], '旁': ['立', '方'],
    '囊': ['口', '襄'], '襄': ['衣', '口'],
    '在': ['才', '土'], '存': ['才', '子'],
    '岛': ['鸟', '山'], '鸟': ['鸟'],
}
_IDS_OPS = {'⿰': 2, '⿱': 2, '⿲': 3, '⿳': 3, '⿴': 2, '⿵': 2, '⿶': 2, '⿷': 2, '⿸': 2, '⿹': 2, '⿺': 2, '⿻': 2}
_SLOTS = {'⿰': ['L', 'R'], '⿱': ['T', 'B'], '⿲': ['L', 'M', 'R'], '⿳': ['T', 'M', 'B'], '⿴': ['O', 'I'], '⿵': ['T', 'O'], '⿶': ['B', 'O'], '⿷': ['R', 'O'], '⿸': ['TL', 'O'], '⿹': ['TR', 'O'], '⿺': ['BL', 'O'], '⿻': ['A', 'B']}


def _parse_ids(s):
    def go(pos):
        if pos >= len(s): return None, pos
        ch = s[pos]
        if ch == '&':
            end = s.find(';', pos)
            tok = s[pos:end + 1] if end != -1 else ch
            return tok, (end + 1 if end != -1 else pos + 1)
        if ch in _IDS_OPS:
            children, p = [], pos + 1
            for _ in range(_IDS_OPS[ch]):
                child, p = go(p)
                children += [child]
            return (ch, children), p
        return ch, pos + 1
    if not s: return None
    tree, _ = go(0)
    return tree


def _valid_comp(c):
    if len(c) != 1: return True
    o = ord(c)
    return o >= 0x2E80 and not (0xE000 <= o <= 0xF8FF or 0xF0000 <= o <= 0x10FFFF)


def _pos_leaves(tree, path=''):
    if tree is None: return set()
    if isinstance(tree, str):
        comp = _RADICAL_NORM.get(tree, tree)
        if comp in NOISE or not _valid_comp(comp): return set()
        return {f'{path}={comp}' if path else comp}
    op, children = tree
    feats = set()
    for i, child in enumerate(children):
        slot = _SLOTS.get(op, [str(j) for j in range(len(children))])[i]
        feats |= _pos_leaves(child, f'{path}.{slot}' if path else slot)
    return feats


def get_pos_feats(char, ids_dict):
    tree = _parse_ids(ids_dict.get(char, {}).get('ids', ''))
    return _pos_leaves(tree) if tree else set()


def _jaccard(a, b):
    if not a and not b: return 0.0
    return len(a & b) / len(a | b)


def build_similarity_index(characters, ids_dict, threshold=0.25):
    pos_map = {c: get_pos_feats(c, ids_dict) for c in characters}
    result = {}
    for char in characters:
        feats = pos_map[char]
        threats = sorted([(other, _jaccard(feats, pos_map[other])) for other in characters if other != char and _jaccard(feats, pos_map[other]) >= threshold], key=lambda item: -item[1])
        result[char] = {'similar': [other for other, _ in threats[:8]]}
    return result


def write_final_components(characters, ids_dict, similar_idx, output_path):
    def _ok(x): return x not in NOISE and (len(x) != 1 or _valid_comp(x))
    def _component_norm(x): return _COMPONENT_REMAP.get(_RADICAL_NORM.get(x, x), _RADICAL_NORM.get(x, x))
    def _component_ok(x): return _ok(_component_norm(x))
    def _direct_components(char):
        seen, result = set(), []
        for item in (ids_dict.get(char, {}).get('decomposition', []) or []):
            if not isinstance(item, dict): continue
            for children in item.values():
                for child in children:
                    parts = []
                    if isinstance(child, str): parts += [child]
                    elif isinstance(child, dict):
                        for nested in child.values():
                            for part in nested:
                                if isinstance(part, str): parts += [part]
                    for part in parts:
                        part = _component_norm(part)
                        if part != char and _component_ok(part) and part not in seen: seen.add(part); result += [part]
        return result
    def _discriminating(char, comps_map):
        my = set(comps_map.get(char, []))
        if not my: return set()
        similar = [other for other in similar_idx.get(char, {}).get('similar', []) if other in comps_map]
        if not similar: return my
        common = my.copy()
        for other in similar: common &= set(comps_map[other])
        return my - common
    def _family_shared(char, comps_map, threshold=0.5):
        my = set(comps_map.get(char, []))
        if not my: return []
        similar = [other for other in similar_idx.get(char, {}).get('similar', []) if other in comps_map]
        if not similar: return []
        counts = defaultdict(int)
        for other in similar:
            for comp in comps_map.get(other, []):
                if comp in my: counts[comp] += 1
        return sorted((comp for comp in my if counts[comp] / len(similar) >= threshold), key=lambda comp: -counts[comp])

    direct_components = {c: _direct_components(c) for c in characters}
    component_map = {c: set(direct_components[c]) for c in characters}
    core_components = {}
    for c in characters:
        disc = _discriminating(c, component_map)
        core_components[c] = [comp for comp in direct_components[c] if comp in disc]
        if direct_components[c] and not core_components[c]: core_components[c] = direct_components[c]

    family = {c: _family_shared(c, component_map) for c in characters}
    family_components = {}
    for c in characters:
        seen, ordered = set(), []
        for comp in family[c]:
            comp = _component_norm(comp)
            if comp != c and _component_ok(comp) and comp not in seen: seen.add(comp); ordered += [comp]
        family_components[c] = ordered

    components_out = {}
    for c in characters:
        target, seen, ordered = set(family_components[c]) | set(core_components[c]), set(), []
        for comp in direct_components[c]:
            if comp in target and comp not in seen: seen.add(comp); ordered += [comp]
        for comp in family_components[c] + core_components[c]:
            if comp not in seen: seen.add(comp); ordered += [comp]
        if c in _SELF_COMPONENT_OVERRIDES: ordered = [c]
        if c in _CHAR_COMPONENT_OVERRIDES: ordered = [comp for comp in _CHAR_COMPONENT_OVERRIDES[c] if _component_ok(comp)]
        if not ordered: ordered = [c]
        components_out[c] = ordered

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f: json.dump(components_out, f, ensure_ascii=False, indent=2)
    non_empty = sum(1 for comps in components_out.values() if comps)
    print(f"  {output_path.name}: {non_empty}/{len(characters)} chars have components")


if __name__ == "__main__":
    with open(MEMODEVICE_DIR / "data_memodevice.json", "r", encoding="utf-8") as f: data = json.load(f)
    with open(REFERENCE_DIR / "ids_dictionary.json", "r", encoding="utf-8") as f: ids_dict = json.load(f)
    characters = [entry['character'] for group in data.values() for entry in group]
    print(f"Processing {len(characters)} characters...")
    print("\nBuilding visual confusable index for final approach...")
    idx = build_similarity_index(characters, ids_dict)
    print("\nWriting final component file...")
    write_final_components(characters, ids_dict, idx, DATA_DIR / "derived" / "components" / "components.json")
